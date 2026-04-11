# FACT — Verified Intelligence Platform
## プロジェクト概要

**コンセプト：「答えを提供するのではなく、考えるきっかけを作る」**
- AIが分析した「考慮事項」を蓄積するプラットフォーム
- SNS・掲示板との差別化：ユーザーはトリガー、AIがコンテンツ品質を保証
- North Star Metric：月間注意喚起タップ数

---

## 現在のファイル構成

```
index.html   — 単一ファイルのプロトタイプ（約13万文字）
```

---

## アーキテクチャ（index.html内部構造）

### 主要データ定数
| 定数 | 役割 |
|------|------|
| `FACT_TOPICS` | 12件のトピック基本情報（id/title/cat/score等） |
| `TOPIC_DATA` | 各トピックの詳細（timeline/perspectives/sources/related） |
| `CATEGORIES` | 12カテゴリ一覧 |
| `SUBS` | サブカテゴリ |
| `ALERTS` | 注意喚起4件 |
| `RANKING` | 急上昇ランキング（day/week） |
| `PICKUP` | ピックアップ3件 |
| `FOLLOWUP` | 続報4件（タイムライン付き） |
| `ALL_SOURCES` | 袴田事件専用ソース11件（articles配列構造） |
| `MEDIA_MASTER` | 35メディア一覧（rank S/A/B） |

### 主要関数
| 関数 | 役割 |
|------|------|
| `goTopic(id)` | IDでトピック詳細に遷移（全遷移の基本） |
| `goTopicDetail(el)` | data-tid属性からトピック詳細に遷移 |
| `getTopicData(id)` | TOPIC_DATAを取得（なければ自動生成） |
| `setSearchQuery(q)` | タイトルからID逆引き→goTopicへ |
| `renderHome()` | ホーム画面 |
| `renderHomeTab(tab)` | alerts/trending/pickup/followup |
| `renderSearch()` | 検索画面（Empty→Results→Detail） |
| `renderSearchResults(p)` | FACTトピックカード一覧 |
| `renderSearchDetail(p)` | 5タブ詳細画面 |
| `renderExplore()` | 記録タブ（depth 0→1→2） |
| `renderSummaryTab(topic)` | 要約タブ |
| `renderTimelineTab(topic)` | 時系列タブ |
| `renderSourcesTab(topic)` | ソースタブ（B案：メディア単位ドリルダウン） |
| `renderPerspectivesTab(topic)` | 多角的視点タブ |
| `renderRelatedTab(topic)` | 関連記事タブ |
| `showAlertByEl(el)` | data属性方式でアラートポップアップ表示 |
| `showPopup(d)` | ポップアップ表示（topicIdあればgoTopic） |
| `openUrl(url)` | window.open wrapper |

### state管理
```javascript
let state = {
  nav: "home",              // home/search/explore/alerts/settings
  homeTab: "alerts",        // alerts/trending/pickup/followup
  searched: false,
  searchQuery: "",
  searchPhase: "results",   // results/detail
  currentTopicId: null,     // ★重要：全タブのデータ取得に使用
  searchTab: 0,             // 0=要約 1=時系列 2=ソース 3=多角的視点 4=関連
  exploreDepth: 0,          // 0=カテゴリ 1=サブ 2=トピック一覧
  sensitivity: 3,           // 注意喚起の感度（1-5）
  ...
}
```

---

## 重要な設計原則

### トピック遷移は必ずIDで行う
```javascript
// ✅ 正しい
goTopic("hakamada_muzai");

// ❌ NG（タイトル文字列が一致しないとFACT_TOPICS[0]になる）
setSearchQuery("袴田事件 再審無罪確定");
```

### onclickはdata属性方式で実装
```javascript
// ✅ 正しい（SyntaxError回避）
data-tid="hakamada_muzai" onclick="goTopicDetail(this)"

// ❌ NG（エスケープ地獄でブラウザSyntaxError）
onclick="state.currentTopicId='hakamada_muzai';..."
```

### showPopup/showAlertByElのパターン
```javascript
// ALERTカードは必ずdata属性方式
data-type="sns" data-msg="..." data-tid="topicId" onclick="showAlertByEl(this)"
```

---

## 現在のトピック一覧（FACT_TOPICS）

| id | title | cat | score |
|----|-------|-----|-------|
| hakamada_muzai | 袴田事件 再審無罪確定 | 司法・裁判 | 92 |
| hormuz_crisis | ホルムズ海峡危機 日本への影響 | 地政学・安保 | 91 |
| microsoft_japan | Microsoft 日本に1兆円AI投資 | 経済・産業 | 88 |
| yosan_2026 | 2026年度本予算 4月11日自然成立 | 政治・行政 | 85 |
| sudden_death_diagnosis | 突然死診断に新手法 | 医療・健康 | 82 |
| march_high_temp | 2026年3月 全国的に高温・少雨 | 科学・環境 | 87 |
| enzai_cf | 冤罪被害者ら 再審制度改正へCF | 社会・事件 | 83 |
| ai_datacenter_japan | AIデータセンター 日本誘致競争 | テクノロジー | 80 |
| kyoiku_2026 | 私立高校授業料実質無償化・給食費無償化 | 教育・子ども | 86 |
| food_price_hike | 原油高・円安で食料品価格が高騰 | 食品・消費者 | 89 |
| tochigi_jishin | 栃木で震度5弱 東北新幹線に遅れ | 災害・インフラ | 84 |
| hakamada_history | 袴田事件が問う日本の刑事司法58年 | 歴史・検証 | 88 |

TOPIC_DATAは hakamada_muzai / hormuz_crisis / microsoft_japan の3件のみ詳細実装。
残り9件は `getTopicData()` が自動生成するフォールバックデータを使用。

---

## ビジネス設計

### 収益モデル
- CM広告3フォーマット（バナー/インタースティシャル/ネイティブ）
- サブスク：無料 / ¥280 / ¥580 / ¥980
- Amazon Associates連携（3箇所）
- 寄付

### APIコスト設計
- 1トピック分析：約$0.09（約13円）
- Claude Sonnet 4.5使用
- キャッシュヒット率70%目標でコスト1/3に
- ユーザー自身のClaude APIキーでコスト負担させる設計も検討中

### Phase 1目標
- MAU 5,000
- 月次収益 ¥278,000
- 月間登録トピック数 1,000件

---

## GitHub Pages
- URL: https://shuichi0725-cmyk.github.io/fact-prototype/
- リポジトリ: shuichi0725-cmyk/fact-prototype
- ブランチ: main / index.html

---

## 注意事項・過去の失敗パターン

1. **onclick内のシングルクォート** → ブラウザSyntaxError → 必ずdata属性方式
2. **encodeURIComponent(JSON.stringify(...))のonclick使用** → TypeError → showAlertByEl方式に統一
3. **関数を別関数の中に誤配置** → JSコードがHTMLとしてレンダリング → 構文チェック必須
4. **TOPIC_DATAなしでタブを表示** → 全トピックが袴田事件データを表示 → getTopicData()を通す
5. **setSearchQueryでタイトル逆引き** → タイトル不一致で失敗 → goTopic(id)を使う
6. **部分修正の繰り返し** → コード崩壊 → 関数単位で完全書き直しが安全

---

## 開発時の確認手順

```bash
# JS構文チェック（必ず実施）
node --check index.html の <script>内容

# 確認すべき関数の存在
grep "function goTopic\|function getTopicData\|function showAlertByEl" index.html

# currentTopicIdの参照確認
grep "currentTopicId" index.html
```
