# Evolution Specification — v0.1

## Selection

自然選択は明示的なfitness関数で順位付けしない。個体は環境中で資源を得て生存・繁殖できた場合のみ子孫を残す。

## Heredity

子は親Genomeの変異コピーを受け継ぐ。v0.1は無性生殖のみ。

## Open-ended expansion path

- sexual crossover
- variable-length genomes
- developmental gene regulation
- epigenetic state
- horizontal gene transfer
- symbiosis
- host/parasite coevolution
- learned-bias inheritance
- cultural inheritance

## Principle

「強い個体」をコードで定義しない。環境条件に対して結果的に増えた形質を適応として観測する。

## Hidden directional pressures (contract 2)

明示的な fitness 関数はないが、次の実装上の性質は結果の方向を与えうる。形質変化を報告するときは、これらを交絡要因として扱う。

- **コスト関数の形。** 基礎代謝と移動コストの係数（`SimulationConfig` の物理）は、どの形質の組み合わせが得かを決める。係数は仮説であり、変えればモデルが変わる。詳細は `GENOME_SPEC.md`。
- **取り合いの規則。** 同じパッチの取り合いは等分である。先着順（contract 1）や強さによる配分では、別の生活史戦略が選ばれうる。これはモデル上の選択である。
- **変異演算子と境界。** 対数正規変異そのものに偏りはないが、反射境界のもとで長い系統は境界の幾何平均へ寄る。
- **体に依存しない摂取量。** `bite_size` は全個体で同じであり、体の大きさと摂取量のトレードオフは進化できない。

contract 1 の既知の偏り（リスト順による採餌の優先権、コストのない遺伝子の境界への張り付き、下向きの中立ドリフト）は contract 2 で解消した。比較結果は `experiments/genesis/README.md` を参照。

## Controls

適応を主張する前に、少なくとも次と比較する。

- `python -m eyggnx.controls`: 変異のみ・選択なしの中立ドリフト基準
- `SimulationConfig(mutate_offspring=False)`: 固定ゲノム対照
- 複数 seed（推奨 ≥ 20）での分布比較
