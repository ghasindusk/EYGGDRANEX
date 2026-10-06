# Contributing to EYGGDRANEX

歓迎する貢献:

- reproducible experiments
- simulation correctness fixes
- performance improvements
- new measurable ecology mechanisms
- documentation and research references

## Rule: emergence before scripting

新しい生態現象を「イベントとして直接発生させる」より、その現象が下位ルールから成立できる設計を優先してください。

## Rule: architecture invariants

すべての変更は [`docs/architecture/INVARIANTS.md`](docs/architecture/INVARIANTS.md) の12項目の不変条件を守ってください。新しい機構を追加する PR では、影響する不変条件と、それを確認するテストを示してください。

## Pull requests

PRには以下を含めてください。

- 変更理由
- 影響範囲
- テスト方法
- 実験挙動を変える場合はSeedと再現手順
- backward-compatibility impact
