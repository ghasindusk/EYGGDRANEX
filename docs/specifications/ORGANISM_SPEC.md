# Organism Specification — v0.1

各個体は以下を持つ。

- unique id
- position `(x, y)`
- energy
- age
- genome
- generation
- parent id

## Tick lifecycle

1. 周辺資源を知覚
2. 最寄りの知覚可能資源へ移動、なければランダム探索
3. 基礎代謝と移動コストを支払う
4. 接触資源を摂取しエネルギーへ変換
5. 生殖閾値を超えていれば子を生成
6. エネルギー枯渇または寿命到達で死亡

このモデルは意図的に単純であり、創発判定の基準系として使う。
