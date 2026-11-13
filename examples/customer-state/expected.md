# 验收判断

- customer-1 的历史支持复购；付款咨询支持当前明确意向，分别保留证据。不能被单一“已购”状态遮蔽。
- 预算保留原话，amount=500、precision=approximate、currency=null、hard_upper_bound=null。不推断价格敏感或 500 内。
- 拒绝范围为 campaign-spring；其他活动联系偏好保留未知/已有依据，不能自动设允许，也不能推成全局拒联。
- 旧 stage 原值与来源缺失保留；不据它补造观察时间。
- customer-2 停止营销，按退货请求与服务授权处理售后，不夹带营销；两个状态同时存在。
- 输出草稿/diff，不声称数据库已更新。
