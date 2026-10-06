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

## Current compliance (simulation contract 1, v0.1.1-alpha)

採用時点で、すべてが満たされているわけではない。満たしていない項目は、既知の逸脱として記録し、simulation contract 2 以降で解消する。

| # | 状態 | 根拠 / 逸脱の内容 |
|---|---|---|
| 1 | ✅ 満たす | 繁殖条件は生存条件と `energy >= reproduction_threshold` のみ（`ORGANISM_SPEC.md`） |
| 2 | ✅ 満たす | 種・役割のラベルはコードに存在しない |
| 3 | ⚠️ 文書化された例外 | 個体はリスト順に行動し、先頭の個体に採餌の優先権がある。`ORGANISM_SPEC.md` に明記し、`test_list_order_decides_feeding_priority` で固定している。解消は contract 2 の判断（NEEDS-HUMAN） |
| 4 | ✅ 満たす | `EnergyLedgerTests`（子への分配、パッチ減少量 = 摂食量） |
| 5 | ⚠️ 既知の逸脱 | `metabolism`・`max_age`・`sensor_range` はコストがなく、clamp 境界へ張り付く（`GENOME_SPEC.md`）。新しい形質を追加するときはこの不変条件を必ず守る |
| 6 | ✅ 満たす | `state_digest()`・プラットフォーム別 golden digest（`tests/golden_digests.json`）。OS 間の一致は主張しない |
| 7 | ❌ 未達 | 全機構が単一の `random.Random` を共有している。乱数の系統分離は contract 2 の判断（NEEDS-HUMAN） |
| 8 | ✅ 満たす | `test_recording_does_not_change_the_trajectory` |
| 9 | ✅ 満たす | `test_reference_seed_runs_to_completion_or_extinction` |
| 10 | ✅ 満たす | ゲノムが作られるのは初期個体の生成時と繁殖時（`mutate`）だけである。学習・文化の層はまだない |
| 11 | ✅ 満たす | LLM の層はない |
| 12 | ✅ 満たす | `v0.1.0-alpha` タグは不変。force-push しない |

## How to apply

- 新しい機構を追加する PR では、影響する不変条件を挙げ、それを守っていることを示すテストを付ける。
- ⚠️ / ❌ の項目を悪化させる変更（例: 新しい順序依存、別機構と共有する乱数の追加、コストのない新形質）は受け入れない。
- ⚠️ / ❌ の項目を解消する変更は軌跡を変えるため、simulation contract の改訂として扱う（CHANGELOG に明記し、golden digest を更新する）。
