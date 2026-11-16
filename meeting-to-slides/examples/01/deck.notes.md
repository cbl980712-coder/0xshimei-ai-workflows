# 演讲提纲备忘：Rust GATs 稳定化评审会（2022-08-31）

> 由 make_presentation.py 自动生成；共 7 页，建议总时长 7 分钟（估算：每页约 1 分钟）。

## 第 1 页　Rust GATs 稳定化评审会（2022-08-31）
- 开场：说明这是哪次会议、谁参加、今天只讲结论和待办。
- 数据来源：功能上线评审｜发言人：jackh726、nikomatsakis、joshtriplett、simulacrum｜来源：Rust 语言组公开纪要，7122 词

## 第 2 页　背景：评审什么
- 这是一份中期汇报：同步 GAT 稳定化现状，并汇总 PR 讨论里提出的问题
- 稳定化 PR 由 jackh726 提交，稳定化提案由 nikomatsakis 撰写
- 提案发出后评论很多，但没有提出提案未覆盖的新问题；分歧在于建议本身

口头补充（原话依据，讲的时候可展开）：
  - 「This is an interim report to bring folks up to date on GAT stabilization and summarize the questions and comments that have been raised.」

## 第 3 页　决策选项（共 4 个）
- 选项一：现在稳定化，之后增量改进（语法、implied bounds、Polonius、where 规则）
- 选项二：等 implied bounds 修好后再稳定
- 选项三：只稳定“生命周期型”GAT，类型型 GAT 另找方案
- 选项四：彻底重新设计 GAT——会上没有人主张这条

口头补充（原话依据，讲的时候可展开）：
  - 「Lifetime-only GATs come up very often and are needed throughout the standard library.」
  - 「Type GATs come up less often, in more abstract framework-y code.」

## 第 4 页　支持与反对的理由
- 支持：已有大量用户在用并受益；bevy、embassy 等框架想借它做更好的抽象
- 反对：implied bounds 缺陷让生命周期 GAT 反而比现有稳定的变通写法更难用
- 担心复杂度：有中级用户表示“试了几次还是没搞懂”
- 担心稳定后长期停在不完美状态；对策：types 团队现在有更多人手

口头补充（原话依据，讲的时候可展开）：
  - 「Appendix A 收集了 PR 讨论里支持者和质疑者的原话。」
  - 「历史上修复难 bug 较慢，例如 normalization under binders。」

## 第 5 页　已知限制与风险
- HRTB（高阶 trait 约束）语法别扭，推断和 implied bounds 有时不可靠
- “能用 / 应该能用但不能 / 不该能用”之间边界不清晰
- 默认约束规则（如 where Self: 'a）不直观，是否提供关闭方式未定
- 已知 bug 修完的时间：jackh726 估计“很可能要一年”

口头补充（原话依据，讲的时候可展开）：
  - 「jackh726: Depends a lot, but it could easily be a year.」

## 第 6 页　结论与建议
- 稳定化提案建议：先稳定，再增量改进（对应选项一）
- 短期缓解：给 GAT 相关报错做专门诊断（jackh726 已有原型）
- 长期：以向后兼容的方式修复 implied bounds、Polonius 等限制
- 注意：这份纪要没有记录最终表决结果

口头补充（原话依据，讲的时候可展开）：
  - 「Jack has been exploring diagnostics and has a prototype that is able to pinpoint the use of GATs as a problem.」

## 第 7 页　下一步与待办
- 后续要靠 3 个大工程：chalk、polonius、GAT 的 implied bounds
- nikomatsakis：相关修复与 chalk 重构绑在一起；jackh726：mir-formality 工作也会覆盖
- 文档调整：josh 建议把“已知限制”放到“主要选项”之前，避免前向引用
- 待澄清：会上提出的 Mark 的 Illegal case 3 等具体用例

口头补充（原话依据，讲的时候可展开）：
  - 「joshtriplett: it sounds like you're saying there will now be 3 major projects over the horizon: chalk, polonius, implied bounds on gats?」
