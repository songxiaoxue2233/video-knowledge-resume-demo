// 静态 Mock 数据：与原型保持一致。未来替换为后端接口返回。
export const stats = [
  { key: 'notes', label: '总笔记数', value: 5, icon: '📖' },
  { key: 'today', label: '今日新增', value: 5, icon: '＋' },
  { key: 'folders', label: '分类数量', value: 1, icon: '□' },
  { key: 'tags', label: '标签数量', value: 10, icon: '◇' }
]

export const folders = [
  { id: 'all', name: '全部笔记', count: 5 },
  { id: 'test-folder', name: '测试文件夹', count: 0 }
]

export const tags = [
  { id: 'study-method', name: '学习方法', count: 1 },
  { id: 'efficiency', name: '效率提升', count: 1 },
  { id: 'time-management', name: '时间管理', count: 1 }
]

export const notes = [
  {
    id: 'note-001',
    title: '一招解决你多年的困扰',
    sourceTitle: '口碑营销为什么比硬广更容易被信任',
    summary: '职场新人必看的5个建议。第一，主动汇报工作进度...',
    platform: '抖音',
    platformType: 'dy',
    date: '2026-07-19 19:21',
    shortDate: '07-19 19:21',
    category: '未分类',
    tags: ['知识管理', '学习方法', '职场成长']
  },
  {
    id: 'note-002',
    title: '这个技巧99%的人都不知道',
    sourceTitle: '这个技巧99%的人都不知道',
    summary: '研究生阶段如何高效阅读文献，第一步：先读摘要...',
    platform: '抖音',
    platformType: 'dy',
    date: '2026-07-19 19:20',
    shortDate: '07-19 19:20',
    category: '未分类',
    tags: ['笔记方法', '知识管理', '读研攻略']
  },
  {
    id: 'note-003',
    title: '早起一年，我的人生发生了什么变化',
    sourceTitle: '早起一年，我的人生发生了什么变化',
    summary: '极简生活的10个小建议。定期清理不用的物品...',
    platform: '小红书',
    platformType: 'xhs',
    date: '2026-07-19 18:36',
    shortDate: '07-19 18:36',
    category: '未分类',
    tags: ['生活方式', '自我提升']
  },
  {
    id: 'note-004',
    title: '学会这个，效率提升10倍',
    sourceTitle: '学会这个，效率提升10倍',
    summary: '今天给大家分享三个超实用的时间管理方法...',
    platform: '抖音',
    platformType: 'dy',
    date: '2026-07-19 18:20',
    shortDate: '07-19 18:20',
    category: '未分类',
    tags: ['效率提升', '时间管理']
  },
  {
    id: 'note-005',
    title: '研究生必看！文献阅读的正确姿势',
    sourceTitle: '研究生必看！文献阅读的正确姿势',
    summary: '更新后的摘要内容测试，适合沉淀为读研方法论...',
    platform: '小红书',
    platformType: 'xhs',
    date: '2026-07-19 18:20',
    shortDate: '07-19 18:20',
    category: '未分类',
    tags: ['笔记方法', '知识管理', '读研攻略']
  }
]

export const detailNote = {
  id: 'note-001',
  title: '口碑营销为什么比硬广更容易被信任',
  author: '品牌增长研究所',
  platform: '抖音',
  publishTime: '2026/07/05 12:42',
  importTime: '2026/07/19 19:21',
  category: '市场营销',
  subCategory: '口碑营销',
  tags: ['市场营销', '信任机制', '用户证言'],
  summary: '视频围绕“口碑营销为什么有效”展开，强调用户不是被品牌自夸说服，而是被第三方经验、真实使用场景和可验证结果降低顾虑。适合沉淀到「市场营销 - 口碑营销」知识分类中。',
  theory: '口碑营销的底层逻辑是“信任转移”：消费者更容易相信相似用户的真实体验，而不是品牌单方面的宣传。有效口碑需要具体场景、真实结果和可验证细节。',
  steps: [
    '先定位目标人群最关心的决策顾虑，例如效果、价格、风险、售后。',
    '收集真实用户反馈，优先保留具体场景、使用前后变化和量化结果。',
    '把反馈整理成“问题 - 使用过程 - 结果 - 推荐理由”的结构。',
    '投放时避免空泛夸张，用用户原话和证据增强可信度。'
  ],
  terms: [
    { name: '口碑营销', desc: '借助用户评价、推荐和使用经验，让潜在用户形成信任并产生购买意愿。' },
    { name: '信任转移', desc: '用户把对“真实使用者”的信任转移到品牌或产品上。' },
    { name: '社会证明', desc: '通过多数人选择、专家背书、用户案例等信号降低决策不确定性。' }
  ],
  cases: {
    good: '用真实用户的“使用场景 + 前后变化 + 具体结果”表达，例如“油皮通勤一整天，下午补妆次数从3次降到1次”。',
    bad: '只写“超好用、闭眼入、全网第一”，没有具体证据，容易被用户识别为硬广。'
  },
  extension: {
    example: '博主举例：护肤品牌把“用户坚持使用28天后的肤感变化”整理成案例，比单纯讲成分浓度更容易让新用户理解价值。',
    confusion: '口碑营销不等于刷好评。前者强调真实经验沉淀和信任建立，后者容易制造虚假繁荣，长期损害品牌可信度。',
    qa: ['没有大量用户评价时，可以先做小样本深访，把3-5个高质量案例写透。', '负面评价不一定要删除，可以提炼为产品改进和风险说明，反而增强真实感。']
  },
  annotations: {
    highlight: '最有价值的是“信任转移”这个概念：口碑的关键不是声音多，而是让潜在用户相信这个经验和自己有关。',
    question: '需要后续查证：不同品类中，用户证言、专家背书、数据报告三种证据的说服力排序是否不同。',
    transfer: '可以迁移到求职作品集、课程推广、护肤成分科普、家居改造案例展示等需要建立信任的内容场景。',
    memory: '口诀：别只说好，讲清“谁用了、怎么用、解决了什么”。'
  },
  quote: '真正有效的口碑，不是替品牌夸自己，而是让用户看到“像我这样的人也解决了这个问题”。'
}
