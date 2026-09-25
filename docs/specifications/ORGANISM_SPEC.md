# Organism Specification — v0.1 (simulation contract 1)

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

## Exact tick semantics (contract 1)

以下は v0.1.0-alpha のコードが実際に行う順序であり、`tests/test_invariants.py` の特性テストで固定している。変更する場合は simulation contract の改訂として扱う（CHANGELOG に明記し、golden digest を更新する）。

1. **資源再生が先。** tick の最初に全パッチが `min(capacity, energy + regen)` で再生する。
2. **個体はリスト順に1体ずつ行動する。** 順序は「生存している既存個体の挿入順、その後に前 tick の出生個体」。先に行動した個体が同じパッチを先に食べるため、リスト前方の個体（古い系統）に採餌上の優先権がある。これは明示的なルールではなくループ順の帰結であり、長期的には進化する生活史戦略（繁殖閾値・子への投資）を左右することが監査で測定されている（30 seed × 10,000 tick で固定順とシャッフル順の繁殖閾値分布が重ならない）。順序の変更は将来の contract 改訂で判断する。
3. **知覚。** `perception_threshold`（既定 0.2）以下のエネルギーのパッチは知覚されない。知覚範囲内では無料・ノイズなしで、最も近いパッチを選ぶ（等距離ならリストで先のパッチ）。
4. **移動とコスト。** 対象がなければ `speed × U(wander_step_range)` のランダム歩行。コスト `metabolism + 移動距離 × movement_cost` を支払う。この時点でエネルギーが 0 以下になっても、まだ死亡判定はしない。
5. **摂食。** `contact_radius`（既定 1.1）以内の最寄りパッチから最大 `bite_size`（既定 3.0、体に依存しない）を取る。コスト支払い後にエネルギーが 0 以下でも、ここで食べて正に戻れば生存する（rescue by feeding）。
6. **生殖。** 生存条件（`energy > 0` かつ `age < max_age`）を満たし、`energy >= reproduction_threshold` なら子を1体生成する（1 tick に最大1体）。親エネルギーの `offspring_fraction` を子へ正確に移し、子は親から `offspring_offset`（既定 1.0）の距離に置かれる。寿命の最終 tick では食べるが生殖はしない。
7. **死亡判定は tick の最後に1回だけ。** `energy <= 0` または `age >= max_age` の個体を除去する。死因の記録（recorder）では starvation を age より優先する。個体のエネルギーは消滅し、死骸・デトリタスは生成されない。
8. **出生個体はその tick には行動しない。** 子は age 0 で次の tick から行動する。

## Controller

GENESIS の行動則は固定の「最寄り資源へ向かう」制御器であり、遺伝しない。進化するのは生理・生活史パラメータ（Genome）だけで、行動戦略そのものは進化しない。行動戦略の創発を主張できるのは、将来 `Controller` のパラメータが遺伝する設計になってからである。
