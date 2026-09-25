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
Resource regen → [per organism, list order] Perceive nearest patch → Move / wander
  → Pay metabolism + movement cost → Eat (≤ bite_size) → Reproduce if threshold met
→ End-of-tick death check → Append newborns
```

The exact order and its consequences are specified in `docs/specifications/ORGANISM_SPEC.md` (simulation contract 1).

## GENESIS modules

- `genome.py` — 遺伝値、突然変異、`GENE_BOUNDS`
- `organism.py` — 個体状態、知覚、採餌、移動、繁殖条件
- `world.py` — 2Dトーラス世界、資源パッチ、再生
- `simulation.py` — tick、出生、死、観測フック、`state_digest()`
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

GENESISでは「脳」を単純な資源指向制御器に限定する。この制御器は遺伝しない。進化するのは Genome のパラメータだけである。Cognition以降で、ニューラルコントローラ・記憶・内発的動機・高次推論層を追加する。

## Adaptation channels

適応の経路を混同しないため、将来の実装は次の規則に従う。

1. **Darwinian heredity.** Genome を書き換えられるのは生殖（変異・将来の交叉/水平伝播）だけである。
2. **Lifetime learning (planned).** 個体の生涯内状態は、明示的にフラグを立てた実験でない限り遺伝しない（Lamarck 的遺伝はデフォルトで禁止）。
3. **Cultural inheritance (planned).** 文化的状態は個体の外、または明示的に伝達される人工物として持つ。
4. **High-level reasoning (planned, optional).** LLM 等は任意の高次層に限定し、既定では無効とする。毎 tick 全個体の「脳」にはしない。決定性の中核の外に置くか、応答を記録して再生可能にする。
