# Architecture Invariants

**Status:** adopted project policy (2026-10-06, approved by SHAR-K)
**Source:** OPUS GENESIS audit, "Invariants to protect" (AI handoff pack, `04_RESULTS/claude/OPUS_GENESIS_AUDIT.md`)

今後のコード変更はすべて、以下の12項目を守らなければならない。守れない変更は、どの不変条件をどう変えるのかを PR に明記し、この文書の改訂として扱う。

## Invariants

1. **No explicit fitness.** 繁殖は、個体自身の資源状態と物理ルールだけで決まる。目標に向けて計算したスコアで繁殖を決めてはならない。
2. **No kinds.** 種・クラス・役割・栄養段階のラベルをコードに持たない。捕食者・被食者・寄生者・共生者は、解析で*観測される*関係であり、シミュレーション内の分岐ではない。
3. **Order neutrality.** 文書化されたルールがない限り、結果がリスト順・挿入順・id 順に依存してはならない（OPUS-001）。
4. **Energy accounting.** エネルギーの変化はすべて、再生（供給源）、散逸（代謝・移動、および将来の明示されたコスト）、移転（摂食・子への分配、および将来の捕食やデトリタス）のいずれかである。これは tick ごとに検証できなければならない。
5. **Trade-offs, not free lunches.** 改善にコストのない遺伝形質は境界まで進む。新しい形質には物理的なコストを持たせるか、意図的に上限を設けない研究用の対照であることを文書化する（OPUS-002）。
6. **Determinism contract.** (version, simulation_contract, seed, config) が同じなら、全状態はビット単位で一致する。contract を変えるときは明示的にバージョンを上げ、新しい golden digest を記録する。
7. **Stream isolation.** 機構を追加しても、無関係な機構の乱数列は変わらない（OPUS-004）。
8. **Observers do not act.** Recorder・メトリクス・可視化は、状態を書き換えず、シミュレーションの乱数列からも引かない。
9. **Extinction is a result, not a failure.** テストは生存を要求しない。
10. **Channel separation.** ゲノムを書き換えるのは繁殖だけである。学習・文化・推論の層は分離し、明示的に有効にしない限り無効とする。
11. **No per-tick LLM.** 言語モデルの層は任意・高レベル・レート制限付きで、決定論的なコアの外に置く。またはその応答を記録してリプレイ可能にする。
12. **Baseline immutability.** `v0.1.0-alpha` とその軌跡は、タグから再現できる状態を保つ。

## Current compliance (simulation contract 2)

採用時（contract 1, v0.1.1-alpha）には #3・#5・#7 が満たされていなかった。contract 2 でこの3つを解消した。

| # | 状態 | 根拠 |
|---|---|---|
| 1 | ✅ 満たす | 繁殖条件は生存条件と `energy >= reproduction_threshold` のみ（`ORGANISM_SPEC.md`） |
| 2 | ✅ 満たす | 種・役割のラベルはコードに存在しない。パッチ・デトリタス・外部データの餌は同じ基質で、性質（`regen` の符号）が違うだけである。外部データの栄養価もファイル名や形式ではなくバイト列の情報量で決まる |
| 3 | ✅ 満たす | 全個体が同じ世界の状態で決定し、取り合いは等分する。`OrderNeutralityTests`（リストの並びを入れ替えても軌跡が同一、取り合いが対称） |
| 4 | ✅ 満たす | `EnergyLedgerTests`（子への分配、パッチ減少量 = 摂食量、個体のエネルギー収支）。デトリタスは死亡時のエネルギーの移転として扱う |
| 5 | ✅ 満たす（係数は仮説） | 代謝と移動コストは物理に移し、`sensor_range`・`max_age`・`speed` には代償がある（`TradeOffTests`）。20 seed × 30,000 tick で境界への張り付きなし（`experiments/genesis/README.md`）。係数は物理的に正当化された値ではない |
| 6 | ✅ 満たす | `state_digest()`・プラットフォーム別 golden digest（`tests/golden_digests.json`）。OS 間の一致は主張しない |
| 7 | ✅ 満たす | 機構ごとの乱数系統（`world`, `founders`, `movement`, `placement`, `mutation`）。外部データの餌は乱数を使わず内容のハッシュで配置する。`StreamIsolationTests`、`test_nutrients_do_not_shift_other_mechanisms` |
| 8 | ✅ 満たす | `test_recording_does_not_change_the_trajectory` |
| 9 | ✅ 満たす | `test_reference_seed_runs_to_completion_or_extinction`、`tests/test_stability.py` |
| 10 | ✅ 満たす | ゲノムが作られるのは初期個体の生成時と繁殖時（`mutate`）だけである。制御器のパラメータは遺伝子だが、生涯の間に書き換わらない。学習・文化の層はまだない |
| 11 | ✅ 満たす | LLM の層はない |
| 12 | ✅ 満たす | `v0.1.0-alpha` / `v0.1.1-alpha` タグは不変。contract 1 の軌跡はタグから再現できる |

## How to apply

- 新しい機構を追加する PR では、影響する不変条件を挙げ、それを守っていることを示すテストを付ける。
- 不変条件を破る変更（例: 新しい順序依存、別機構と共有する乱数、コストのない新形質）は受け入れない。
- 軌跡を変える変更は simulation contract の改訂として扱う（CHANGELOG に明記し、golden digest を更新する）。
