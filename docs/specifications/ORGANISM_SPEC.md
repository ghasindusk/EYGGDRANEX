# Organism Specification — v0.2 (simulation contract 2)

各個体は以下を持つ。

- unique id
- position `(x, y)`
- energy
- age
- genome
- generation
- parent id

## Tick lifecycle

1. 周辺資源を知覚する
2. 遺伝する制御器で行き先を決める（全個体が同じ世界の状態を見て決める）
3. 移動し、基礎代謝と移動コストを支払う
4. 接触した資源を摂取する（取り合いは等分）
5. 生殖閾値を超えていれば子を生成する
6. エネルギー枯渇または寿命到達で死亡する

このモデルは意図的に単純であり、創発判定の基準系として使う。

## Exact tick semantics (contract 2)

以下はコードが実際に行う順序であり、`tests/test_invariants.py` の特性テストで固定している。変更する場合は simulation contract の改訂として扱う（CHANGELOG に明記し、golden digest を更新する）。contract 1 の挙動はタグ `v0.1.1-alpha` から再現できる。

1. **資源の更新が先。** tick の最初に全パッチが `max(0, min(capacity, energy + regen))` で更新される。再生するパッチは `regen > 0`、デトリタスは `regen < 0`（減衰）で、空になったデトリタスはここで取り除かれる。
2. **順序に依存しない意思決定。** 全個体が、同じ世界の状態に対して行き先（intent）を決める。ある個体の行動を、同じ tick の別の個体が先に見ることはない。個体は id 順に保持され、乱数も id 順に機構ごとの系統から引く。乱数は独立同分布なので、どの個体がどの乱数を受け取っても優先権は生じない。`organisms` の並びを入れ替えても軌跡は変わらない（`test_list_order_does_not_change_the_trajectory`）。
3. **知覚。** `perception_threshold`（既定 0.2）以下のエネルギーのパッチは知覚されない。知覚範囲内では、ノイズはない。ただし知覚範囲の広さは基礎代謝として支払う（下記）。
4. **行き先の決定（制御器）。** 知覚範囲内のパッチから `energy / (1 + distance_aversion × distance)` が最大のものへ向かう（同点なら近い方、さらに同点ならリストで先のパッチ）。移動距離は `min(speed, 距離)`。何も見えなければ、ランダムな方向へ `speed × wander_step` 進む。`distance_aversion` と `wander_step` は遺伝子である。
5. **移動とコスト。** 全個体が移動したあと、各個体は `基礎代謝 + 移動距離 × movement_cost × speed` を支払う。基礎代謝は `base_metabolism + sensor_cost × sensor_range + longevity_cost × max_age`。この時点でエネルギーが 0 以下になっても、まだ死亡判定はしない。
6. **摂食（取り合いは等分）。** 各個体は `contact_radius`（既定 1.1）以内の最寄りパッチを食べる。同じパッチを食べる個体が k 体いて、パッチの残量が `k × bite_size` 以上なら全員が `bite_size`（既定 3.0、体に依存しない）を得る。足りなければ残量を k 等分する。先に行動した個体の優先権はない。コスト支払い後にエネルギーが 0 以下でも、ここで食べて正に戻れば生存する（rescue by feeding）。
7. **生殖。** 生存条件（`energy > 0` かつ `age < max_age`）を満たし、`energy >= reproduction_threshold` なら子を1体生成する（1 tick に最大1体）。親エネルギーの `offspring_fraction` を子へ正確に移す。子の位置は `placement` 系統、子の遺伝子は `mutation` 系統の乱数で決まる。寿命の最終 tick では食べるが生殖はしない。
   - **進化の報酬（任意・実験、`evolution_reward`、既定は無効）。** 不変条件 #1・#5 を意図的に破るモード。個体は生涯に食べたエネルギー（`intake`）を持ち、生殖の時点の 1 tick あたりの摂取量が、自分が生まれたときの親の摂取量を上回っていれば「進化した」とする。進化した個体は、強い子（基礎代謝 ×0.8、生まれるときの変異の幅 ×1.4）を 1 + `evolution_bonus_offspring`（既定 1）体産む。2体目以降の子も、そのときの親のエネルギーの `offspring_fraction` を親から受け取る。進化していない個体の子は弱く（基礎代謝 ×1.2、変異の幅 ×0.6）、確率 `evolution_drop_probability`（既定 0.4）で生まれない。そのときも親は子の分のエネルギーを失う。生まれるかどうかは専用の `evolution` 系統の乱数で決める。初期個体は親がないので通常どおり生殖する。
8. **死亡判定は tick の最後に1回だけ。** `energy <= 0` または `age >= max_age` の個体を除去する（`max_age` は連続値）。死因の記録（recorder）では starvation を age より優先する。`detritus_fraction > 0` のとき、寿命で死んだ個体は残りエネルギーのその割合を、`detritus_decay` ずつ減衰するデトリタス（再生しないパッチ）として残す。既定は 0（無効）で、そのときエネルギーは消滅する。
9. **出生個体はその tick には行動しない。** 子は age 0 で次の tick から行動する。

## Random streams

乱数は機構ごとの系統（`world`, `founders`, `movement`, `placement`, `mutation`）から引く。各系統は `(seed, 名前)` から SHA-256 で導出した独立の `random.Random` である。ある機構を変えたり追加したりしても、他の機構が受け取る乱数は変わらない（`StreamIsolationTests`）。

## Controller

制御器は `eyggnx.controller.Controller` プロトコルで、`decide(organism, world, rng) -> Intent` を実装する。世界の状態を読むだけで、変更はしない。既定の `ForagingController` のパラメータ（`distance_aversion`, `wander_step`）は遺伝するため、採餌戦略（近場を優先するか、豊かなパッチまで行くか、どれだけ探索するか）は進化しうる。ただし戦略の形（スコア関数の形）は固定であり、行動の「形」そのものの創発を主張できるのは、制御器の構造が遺伝する設計（例: ニューラル制御器）になってからである。
