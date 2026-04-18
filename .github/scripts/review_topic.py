#!/usr/bin/env python3
"""
FACT Topic Registration Review Script
GitHub Actions から呼び出される。Issue 内容を Claude で審査し、承認時に PR を自動生成する。
"""

import os
import json
import re
import sys
import base64
import requests
import anthropic

# ── 環境変数 ──────────────────────────────────────────────
GITHUB_TOKEN     = os.environ['GITHUB_TOKEN']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
REPO             = os.environ['GITHUB_REPOSITORY']
ISSUE_NUMBER     = int(os.environ['ISSUE_NUMBER'])
ISSUE_BODY       = os.environ['ISSUE_BODY']
ISSUE_TITLE      = os.environ.get('ISSUE_TITLE', '')

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

GH_HEADERS = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
}

# ── GitHub API ヘルパー ──────────────────────────────────
def gh(method, path, **kwargs):
    url = f'https://api.github.com/repos/{REPO}/{path}'
    resp = getattr(requests, method)(url, headers=GH_HEADERS, **kwargs)
    resp.raise_for_status()
    return resp.json()

def post_comment(body):
    gh('post', f'issues/{ISSUE_NUMBER}/comments', json={'body': body})

def remove_label(label):
    requests.delete(
        f'https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/labels/{label}',
        headers=GH_HEADERS
    )

def get_file(path, ref='main'):
    data = gh('get', f'contents/{path}?ref={ref}')
    content = base64.b64decode(data['content']).decode('utf-8')
    return json.loads(content), data['sha']

def put_file(path, content_str, message, sha, branch):
    gh('put', f'contents/{path}', json={
        'message': message,
        'content': base64.b64encode(content_str.encode('utf-8')).decode('ascii'),
        'sha': sha,
        'branch': branch,
    })

def get_main_sha():
    return gh('get', 'git/ref/heads/main')['object']['sha']

def create_branch(name, sha):
    try:
        gh('post', 'git/refs', json={'ref': f'refs/heads/{name}', 'sha': sha})
    except requests.HTTPError as e:
        if e.response.status_code != 422:  # 422 = already exists
            raise

def create_pr(branch, title, body):
    return gh('post', 'pulls', json={
        'title': title,
        'body': body,
        'head': branch,
        'base': 'main',
    })

# ── Issue body パーサー ──────────────────────────────────
def parse_issue_body(body):
    """GitHub Issue テンプレートのレスポンスを dict に変換"""
    sections = {}
    current_key = None
    current_lines = []

    for line in body.split('\n'):
        if line.startswith('### '):
            if current_key is not None:
                sections[current_key] = '\n'.join(current_lines).strip()
            current_key = line[4:].strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = '\n'.join(current_lines).strip()

    return sections

# ── Claude 審査 ──────────────────────────────────────────
REVIEW_PROMPT = """あなたはFACT（信頼できるニュースを整理するファクトチェックサービス）のコンテンツ審査員です。
以下のトピック登録申請を審査し、結果をJSONで返してください。

## 却下条件（一つでも該当すれば却下）
- 芸能人・著名人の私生活（不倫・スキャンダル・恋愛・離婚）
- 特定個人への攻撃・誹謗中傷・個人情報の暴露
- ゴシップ・週刊誌的な内容
- フェイクニュースサイトや信頼性の低いソースのみが根拠
- 既存トピックと実質的に重複

## 承認条件（すべて満たすこと）
- 政治・経済・科学・社会制度・国際情勢等の公共的トピック
- 信頼できるメディア（新聞・通信社・公共放送・学術機関等）が複数報道
- 社会的意義があり、ファクトチェックの対象として適切

## 既存トピック一覧（重複チェック用）
{existing_topics}

## 登録申請内容
{issue_data}

## 出力
以下のJSON形式のみを返してください（マークダウンや説明文は不要）:
{{
  "approved": true,
  "reason": "承認または却下の理由（日本語、100字以内）",
  "duplicate_id": null,
  "topic_id": "snake_case英語のID（例: hormuz_crisis）",
  "meta_entry": {{
    "id": "topic_id と同じ",
    "title": "トピックタイトル",
    "cat": "カテゴリ",
    "subcat": "サブカテゴリ",
    "score": 85,
    "sourceCount": 3,
    "date": "基準日",
    "summary": "サマリー",
    "tags": ["タグ1", "タグ2"],
    "alert": null
  }},
  "detail_sources": [
    {{
      "id": 0,
      "lang": "ja",
      "org": "組織名",
      "type": "メディアタイプ",
      "score": 95,
      "keyClaim": "このソースの主張（1〜2文）",
      "articles": [
        {{
          "title": "記事タイトル",
          "date": "記事日付",
          "url": "URL",
          "summary": "要約"
        }}
      ]
    }}
  ]
}}

scoreの目安: NHK=97, 共同通信=96, 時事通信=94, 朝日=91, 読売=90, 毎日=91, 日経=92, ロイター=96, AP=95, Bloomberg=93"""


def review_with_claude(issue_data, existing_topics):
    existing_list = [{'id': t['id'], 'title': t['title']} for t in existing_topics]
    prompt = REVIEW_PROMPT.format(
        existing_topics=json.dumps(existing_list, ensure_ascii=False, indent=2),
        issue_data=json.dumps(issue_data, ensure_ascii=False, indent=2),
    )

    message = client.messages.create(
        model='claude-opus-4-7',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = message.content[0].text.strip()
    # JSON ブロックが含まれる場合は抽出
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    return json.loads(json_match.group(1) if json_match else text)


# ── メイン処理 ──────────────────────────────────────────
def main():
    sections = parse_issue_body(ISSUE_BODY)

    issue_data = {
        'title':    sections.get('トピックタイトル', ''),
        'category': sections.get('カテゴリ', ''),
        'subcat':   sections.get('サブカテゴリ', ''),
        'date':     sections.get('基準日', ''),
        'summary':  sections.get('サマリー（200字以内）', ''),
        'tags':     sections.get('タグ（カンマ区切り、3〜5個）', ''),
        'sources':  sections.get('ソース情報', ''),
        'alert':    sections.get('アラート（任意）', ''),
    }

    # 既存トピック読み込み
    try:
        meta, _ = get_file('data/topics_meta.json')
        existing_topics = meta['FACT_TOPICS']
        detail_data, _ = get_file('data/topics_detail.json')
    except Exception as e:
        post_comment(f'⚠️ データ読み込みエラー: {e}')
        sys.exit(1)

    # Claude 審査
    try:
        result = review_with_claude(issue_data, existing_topics)
    except Exception as e:
        post_comment(f'⚠️ 審査中にエラーが発生しました: {e}')
        sys.exit(1)

    # 却下
    if not result.get('approved'):
        reason   = result.get('reason', '理由不明')
        dup_id   = result.get('duplicate_id')
        comment  = f'## ❌ 登録申請 却下\n\n**理由:** {reason}\n'
        if dup_id:
            comment += f'\n**重複している既存トピック:** `{dup_id}`'
        post_comment(comment)
        remove_label('topic-registration')
        return

    # 承認 → PR 生成
    topic_id    = result['topic_id']
    meta_entry  = result['meta_entry']
    branch_name = f'topic/register-{topic_id}'

    main_sha = get_main_sha()
    create_branch(branch_name, main_sha)

    # topics_meta.json を更新
    meta_on_branch, meta_sha_b = get_file('data/topics_meta.json', ref=branch_name)
    meta_on_branch['FACT_TOPICS'].append(meta_entry)
    put_file(
        'data/topics_meta.json',
        json.dumps(meta_on_branch, ensure_ascii=False, indent=2),
        f'feat: トピック登録 - {meta_entry["title"]}',
        meta_sha_b,
        branch_name,
    )

    # topics_detail.json を更新
    detail_on_branch, detail_sha_b = get_file('data/topics_detail.json', ref=branch_name)
    detail_on_branch['TOPIC_DATA'][topic_id] = {'sources': result['detail_sources']}
    put_file(
        'data/topics_detail.json',
        json.dumps(detail_on_branch, ensure_ascii=False, indent=2),
        f'feat: ソースデータ追加 - {topic_id}',
        detail_sha_b,
        branch_name,
    )

    # PR 作成
    pr = create_pr(
        branch_name,
        f'[TOPIC] {meta_entry["title"]}',
        f'## 新規トピック登録\n\n'
        f'**トピックID:** `{topic_id}`  \n'
        f'**カテゴリ:** {meta_entry["cat"]} / {meta_entry["subcat"]}  \n'
        f'**スコア:** {meta_entry["score"]}  \n'
        f'**ソース数:** {meta_entry["sourceCount"]}  \n\n'
        f'**審査結果:** ✅ Claude API による自動審査で承認  \n'
        f'**理由:** {result["reason"]}  \n\n'
        f'closes #{ISSUE_NUMBER}',
    )

    post_comment(
        f'## ✅ 登録申請 承認\n\n'
        f'**審査理由:** {result["reason"]}\n\n'
        f'**自動生成PR:** {pr["html_url"]}\n\n'
        f'管理者がPRをレビューしてマージすると登録完了です。'
    )


if __name__ == '__main__':
    main()
