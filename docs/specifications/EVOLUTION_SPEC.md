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

## Hidden directional pressures (known in contract 1)

明示的な fitness 関数はないが、次の実装上の性質は結果の方向を与えうる。形質変化を報告するときは、これらを交絡要因として扱う。

- **更新順。** リスト前方の個体が先に食べる。固定順とシャッフル順では、進化する繁殖閾値・子への投資・世代交代の速さが大きく異なる（30 seed × 10,000 tick で分布が重ならない）。詳細は `ORGANISM_SPEC.md`。
- **コストのない遺伝子。** 対価のない形質は長期的に clamp 境界へ移動する。詳細は `GENOME_SPEC.md`。
- **変異演算子の偏り。** 選択がなくても中立ドリフトは下向きに働く。

## Controls

適応を主張する前に、少なくとも次と比較する。

- `python -m eyggnx.controls`: 変異のみ・選択なしの中立ドリフト基準
- `SimulationConfig(mutate_offspring=False)`: 固定ゲノム対照
- 複数 seed（推奨 ≥ 20）での分布比較
