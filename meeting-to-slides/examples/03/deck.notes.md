# 演讲提纲备忘：Return Type Notation（RTN）设计评审

> 由 make_presentation.py 自动生成；共 7 页，建议总时长 7 分钟（估算：每页约 1 分钟）。

## 第 1 页　Return Type Notation（RTN）设计评审
- 开场：说明这是哪次会议、谁参加、今天只讲结论和待办。
- 数据来源：语法方案评审｜发言人：nikomatsakis、pnkfelix、scottmcm、tmandry、Yosh、eholk、TC｜来源：Rust 语言组公开纪要，5266 词

## 第 2 页　要解决什么问题
- “send bound”问题：trait 里的 async fn 返回的 future 没法方便地要求 Send
- async WG 的案例研究：不解决它就稳定化，很多场景不够用
- 目标：2023 年交付“可用（不完美）”的 trait 内 async fn
- 提案：RTN，写法如 T: Trait<m(): Send>，目前只实现了这一种形式

口头补充（原话依据，讲的时候可展开）：
  - 「We call this the 'send bounds' problem. In fact, the problem is more general, and applies to any -> impl Trait method defined in a trait.」

## 第 3 页　实践反馈
- 简单场景下容易解释、“还行”；复杂场景（多个方法）不好扩展
- 变通：定义 trait 别名，例如 SendHealthCheck，Tower 计划把别名作主 trait
- 已有 proc macro 减少样板代码（impl_trait_utils）
- 限制：只适用 RPITIT 方法、只支持生命周期参数

口头补充（原话依据，讲的时候可展开）：
  - 「how many times do we have to say Send?」

## 第 4 页　各方观点
- nikomatsakis：它首先是“构建块”，但也希望简单场景可用、讲得清楚；觉得 ::return 太笨重
- pnkfelix：强烈建议别用 foo(): Send，考虑 foo(...): Send，为将来区分参数留余地
- eholk / tmandry：::Output 复用既有概念，但必须靠宏、不会有人手写
- TC：不反对括号，但反对“稳定化却不推广到所有类型位置”，会造成不规则

口头补充（原话依据，讲的时候可展开）：
  - 「scottmcm: ::return feels very long.」
  - 「Yosh：它是否只是高级用户用的构建块？」

## 第 5 页　风险与分歧
- foo() 看起来像表达式却是类型，可能与 const generics 混淆
- “太窄”：只能放在 where 子句；“太宽”：任意 bound 都允许（YAGNI）
- 关联类型 bound 语法本身还不稳定（E0658），是否在此依赖它
- 后继特性要 6 个月到 1 年才能稳定，现在的选择得“忍一阵”

口头补充（原话依据，讲的时候可展开）：
  - 「scottmcm: Are we confident that we want to use that syntax here if we've not stabilized it for normal associated type bounds?」

## 第 6 页　备选方案对比
- RTN：T::m(): Send——简洁，已实现，但括号语义有争议
- ::Output / 高阶默认：复用 Fn 的 Output 概念，需放宽生命周期省略；对新手不直观
- ::return：太长，在 bound 里写成 foo::return: Send 被批“很糟”
- type-of：编译器里的实验特性（从未走 RFC），比 RTN 复杂得多

口头补充（原话依据，讲的时候可展开）：
  - 「nikomatsakis: ::return feels like the worst of both worlds to me. Special and complex.」

## 第 7 页　结论与下一步
- 会上倾向：RTN 作为构建块先行，不追求完美易用
- 待定：是否改成 foo(..): Send 以便将来扩展
- 待做：用宏（如 Send 简写）降低样板；补文档
- 注意：纪要没有记录最终表决，以上为讨论倾向而非决议

口头补充（原话依据，讲的时候可展开）：
  - 「Tl;DR is Send Trait as a shorthand for Trait<fn1(): Send, fn2(): Send> + Send.」
  - 「tmandry: yes! not crates.io. Needs docs.」
