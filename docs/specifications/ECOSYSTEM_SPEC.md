# Ecosystem Specification

## GENESIS

環境は2Dトーラス空間で、食べられるものはすべて「位置とエネルギーを持つ基質」（`ResourcePatch`）である。種類のラベルはなく、性質の違いで振る舞いが決まる。

| 基質 | `regen` | 出どころ | 既定 |
|---|---|---|---|
| 再生する資源パッチ | > 0 | 初期配置（`world` 乱数系統） | 55 個 |
| デトリタス | < 0（減衰） | 寿命で死んだ個体の残りエネルギー | 無効（`detritus_fraction = 0`） |
| 外部データの餌 | = 0（有限・安定） | `nutrient_dir` 直下のファイル | 無効（`nutrient_dir = None`） |

再生しない基質（`regen <= 0`）と、有限の貯蔵（`reservoir`）を使い切った基質は、エネルギーが 0 になると世界から取り除かれる。捕食・病原体・共生は未実装。

## External data nutrients

`SimulationConfig.nutrient_dir`（CLI では `--nutrient-dir DIR`）を指定すると、そのディレクトリ直下のファイルが餌になる（`eyggnx.nutrients`）。

- **読むだけ。** 直下の通常ファイルを名前順に、最大 `nutrient_max_files` 個・各 `nutrient_max_bytes` バイトまで読む。サブディレクトリとシンボリックリンクは読まない。データの実行・解釈・ネットワークアクセスはしない。
- **栄養価は情報量。** エネルギー = `min(nutrient_max_energy, zlib 圧縮後のバイト数 × nutrient_energy_per_byte)`。同じ内容の繰り返しは栄養が少なく、情報の多いデータほど栄養が多い。ファイル名・拡張子・形式は使わない（不変条件 #2）。
- **位置は内容から決まる。** 内容の SHA-256 から座標を決めるため、乱数を消費せず、他の機構の乱数を変えない（不変条件 #7）。同じ内容のファイルは同じ場所に置かれる。
- **分割（任意）。** `nutrient_chunk_bytes > 0` のとき、各ファイルをその大きさの断片に分け、断片ごとに別の餌にする。エネルギーと位置は断片ごとに決まるので、大きなファイルが1点に集中せず世界に散らばる。上限 `nutrient_max_energy` も断片ごとにかかる。断片をまたぐ重複は圧縮で除かれないため、分割すると合計エネルギーは少し増える。
- **ゆっくり放出（任意）。** `nutrient_release_rate > 0` のとき、餌のエネルギーは有限の貯蔵（`ResourcePatch.reservoir`）に入り、表に出るのは最大 `nutrient_release_capacity` まで、貯蔵から1 tick あたり `nutrient_release_rate` ずつ補充される。分解されながら少しずつ食べられる基質に相当する。合計エネルギーは一度に出す場合と同じで、貯蔵から表への移動は基質内部の移転である（不変条件 #4）。貯蔵を持つ基質だけ `state_digest()` に貯蔵量を含めるので、使わない実行の digest は変わらない。
- **再生しない。** 食べ尽くされると消える。Recorder の `finite_substrate_energy` は、まだ残っている有限の餌（デトリタスを含む）の合計である。データだけの世界（`resource_patches = 0`）では餌が有限なので、個体群はいずれ絶滅する。これは有効な結果である。
- **再現性。** ファイル名・サイズ・読んだバイト数・SHA-256・エネルギーの一覧（manifest）とその digest を `Simulation.nutrient_manifest` と run record の `nutrients` に記録する（不変条件 #6）。同じ digest なら同じ餌である。

一度に出すと、餌の多い世界では出生が急増したあと一斉に死ぬ（ブームと崩壊）。ゆっくり放出するとこれが和らぎ、データだけの世界での存続時間が延びる（`experiments/nutrients/README.md`）。既定は互換性のため一度に出す設定のままである。

将来、エネルギーがベクトル（複数の化学）になったら、バイトの分布を餌の化学組成として使い、どのデータを食べられるかが形質として進化できるようにする。

## Planned ecology

- renewable and exhaustible resources
- trophic layers
- predation
- scavenging
- parasitism
- mutualism
- competition
- environmental stress
- disease / immune dynamics
- ecological succession
- niche construction

将来も「捕食者クラス」を直接置くのではなく、代謝・摂取対象・攻撃/防御・エネルギー収支の組み合わせから捕食関係が成立する設計を優先する。
