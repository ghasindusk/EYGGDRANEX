# System Architecture

## Layer model (long-term, includes planned layers)

```text
World / Physics / Resource Field
            ↓
       Perception
            ↓
Genome → Development (planned) → Organism State
            ↓              ↓
      Metabolism ← Drives / Memory (planned)
            ↓              ↓
        Controller → Action
            ↓
   Environment Feedback
            ↓
Reproduction / Mutation / Death
            ↓
      Population Change
```

## GENESIS pipeline (what the code actually does)

```text
Resource update (regen / detritus decay)
  → [all organisms, same world state] Perceive → Controller decides an Intent
  → Act: move, pay basal metabolism + movement cost
  → Resolve feeding: contested patches are shared equally
  → Reproduce if threshold met → End-of-tick death check (+ optional detritus)
  → Append newborns
```

The exact order and its consequences are specified in `docs/specifications/ORGANISM_SPEC.md` (simulation contract 2).

## GENESIS modules

- `genome.py` — 遺伝子テーブル `GENES`（名前・既定値・境界）、対数正規・反射型の突然変異、`GENE_BOUNDS`
- `controller.py` — `Controller` プロトコルと遺伝する `ForagingController`（知覚 → `Intent`）
- `organism.py` — 個体状態、行動の適用とコスト、基礎代謝、繁殖
- `world.py` — 2Dトーラス世界、資源パッチ（再生パッチとデトリタス）、空間グリッドによる知覚
- `simulation.py` — tick（決定 → 行動 → 摂食の解決）、乱数系統、出生、死、観測フック、`state_digest()`
- `stability.py` — 長時間・複数 seed の安定性実行と構造的不変条件のチェック
- `nutrients.py` — 外部データの餌（ディレクトリ直下のファイルを読むだけで基質にする）
- `config.py` — `SimulationConfig`（全定数とその既定値）、`ExperimentSpec`、`SIMULATION_CONTRACT`
- `validation.py` — 公開入力の境界チェック（乱数を消費しない）
- `recorder.py` — 観測専用レコーダー（時系列・系統イベント）
- `controls.py` — 中立ドリフト基準などの対照条件
- `run_record.py` — バージョン付き run record（seed・設定・来歴）
- `cli.py` — 再現可能な実験起動

## Outputs and metric semantics

- `Snapshot.births` / `deaths` は累積値。`max_generation` は**生存個体の中での**最大世代であり、過去の最大値ではない。個体が0のときの平均値は 0.0 の番兵値である。
- `Simulation.run(n)` は個体が絶滅した tick で停止する。創始個体0で始めた場合も、1 tick 進んでから停止する。
- 系統（死亡個体を含む）と遺伝値の分散・境界占有率は `Recorder` の出力から得る。

## Controller boundary

GENESISでは「脳」を単純な採餌制御器に限定する。制御器のパラメータ（`distance_aversion`, `wander_step`）は遺伝するが、スコア関数の形は固定である。制御器は `Controller` プロトコルの背後にあり、Cognition 以降でニューラルコントローラ・記憶・内発的動機・高次推論層に置き換えられる。

## Seams for ECOLOGY (v0.2)

- **決定と解決の分離。** 制御器は `Intent` を返すだけで、世界を変えるのは `Simulation` である。捕食や競合の解決規則はここに追加する。
- **空間インデックス。** `World` は一様グリッドで知覚を高速化する（結果は全探索と同一）。個体間の相互作用を入れるときは、個体も同じグリッドに載せる。
- **基質としての資源。** パッチもデトリタスも「位置とエネルギーを持つ基質」であり、種類のラベルはない。捕食は「生きた基質を摂取すること」として後から追加できる。
- **遺伝子テーブル。** 遺伝子の追加は `GENES` に1行足すだけで、変異・記録・境界判定に反映される。
- **機構ごとの乱数系統。** 新しい機構は自分の系統を持ち、既存の機構の乱数を変えない。
- 未着手: エネルギーのベクトル化（複数の化学）、複数の親を持つ系統。

## Adaptation channels

適応の経路を混同しないため、将来の実装は次の規則に従う。

1. **Darwinian heredity.** Genome を書き換えられるのは生殖（変異・将来の交叉/水平伝播）だけである。
2. **Lifetime learning (planned).** 個体の生涯内状態は、明示的にフラグを立てた実験でない限り遺伝しない（Lamarck 的遺伝はデフォルトで禁止）。
3. **Cultural inheritance (planned).** 文化的状態は個体の外、または明示的に伝達される人工物として持つ。
4. **High-level reasoning (planned, optional).** LLM 等は任意の高次層に限定し、既定では無効とする。毎 tick 全個体の「脳」にはしない。決定性の中核の外に置くか、応答を記録して再生可能にする。

## Invariants

プロジェクト全体で守る12項目の不変条件と、現時点での達成状況は [`INVARIANTS.md`](INVARIANTS.md) にある。
