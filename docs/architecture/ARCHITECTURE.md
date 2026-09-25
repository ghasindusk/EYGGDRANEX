# System Architecture

## Layer model

```text
World / Physics / Resource Field
            ↓
       Perception
            ↓
Genome → Development → Organism State
            ↓              ↓
      Metabolism ← Drives / Memory
            ↓              ↓
        Controller → Action
            ↓
   Environment Feedback
            ↓
Reproduction / Mutation / Death
            ↓
      Population Change
```

## GENESIS modules

- `genome.py` — 遺伝値、突然変異
- `organism.py` — 個体状態、知覚、採餌、移動、繁殖条件
- `world.py` — 2Dトーラス世界、資源パッチ、再生
- `simulation.py` — tick、出生、死、観測
- `cli.py` — 再現可能な実験起動

## Future boundaries

GENESISでは「脳」を単純な資源指向制御器に限定する。Cognition以降で、ニューラルコントローラ・記憶・内発的動機・高次推論層を追加する。
