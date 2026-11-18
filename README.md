# 晨露花市 · 拍价留样簿

晨露花市有8位验级员、3个交易席位，每天清晨接收种植户鲜切花。过去筐数写在到场单、等级记在瓶插簿、报价记在白板，容易把同一筐重复挂给两个标的；竞价截止靠口头喊停，争议后直接改原付款表，种植户难以核对退款。此应用接收采切/到场记录，连起瓶插留样、等级底价、场次竞价、留样复判与货款补退。上游是种植户筐贴与验花记录，下游是交易席、花店买方与种植户结算员。

Python FastAPI、原生HTML/CSS/JS ES modules、PostgreSQL16 READ COMMITTED、Redis队列与独立Python worker、Nginx，恰好5服务。

## 启动与账号

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18234 ，API http://localhost:19234/docs ，数据库17734；短名floral-auction，子网10.221.35.0/24。`.env.example`列出端口/短名/JWT/seed/网络。`docker compose down`停止，`docker compose down -v --remove-orphans`清除演示库。

|角色|邮箱 / 统一口令 Flowers2026!|允许动作|
|---|---|---|
|operator 验级员|operator@chenlu.demo|登记到场/留样、估级、封存瓶插终点、占筐挂场、记录买方报价、申请争议|
|supervisor 拍卖主管|supervisor@chenlu.demo|全部日常动作；筐贴备注核对、核级、场次/时钟、截标/撤场、留样复判、生成结算与登记补退回单|
|viewer 观察席|viewer@chenlu.demo|六页、档案与审计读取；全部写接口后端403|

JWT8小时，PBKDF2盐化口令；Trace中间件请求ID、Burst每IP每分钟360请求、审计actor/action。演示部署需更换默认JWT和库口令。

## 六个业务模块

1. **采切批次与到场分筐**：Consignment唯一code，种植户/品种/采切与到场时间/筐数/每筐支数。到场必须在采切后48小时内且不晚于业务时钟。数量建立后不可任意改写，主管只能修筐贴备注。挂场和成交合计占筐不得超实收。
2. **瓶插留样与寿命估级（双版本换版）**：VaseSample关联到场单，唯一留样签，成熟度、杆长、冷藏小时不得超过采后小时。recorded→queued→running→ready或failed，worker真实估级后主管核定A/B/C，保留模型建议与人工核级。实际瓶插终点只能封存一次；争议使用冻结快照，不覆盖旧证据。估级分两版：`v1-synthetic`旧版（固定合成数据训练，初始生效）与`v2-sealed`新版（仅用已封存实际瓶插终点训练的候选版）。
   - **按到场批固定留出**：封存留样最多的到场批整批选为固定留出（并列取到场单id最小者），该批留样两版都不用于训练；首次评估选定后跨评估沿用同一到场批。
   - **换版规则**：主管在留样页发起换版，两版在同一组固定留出留样上比平均绝对误差（MAE），新版MAE不劣于（`<=`）旧版才把新版置为active、旧版archived；否则沿用旧版，每次评估（含失败与理由）落`model_evaluations`，已切换后拒绝重复换版，未切换可重评。封存/训练留样各不足2条时拒绝评估。
   - **版本固定与不重复**：留样送估（estimate）时即把当时active版本写入`vase_samples.model_version`；worker按该列取模型，中断重试不改换版本，且非queued态任务直接跳过，不重复出结果。历史留样即使换版后仍保留其原估级版本与依据，已核定等级不受影响。
   - 留样页可发起换版、查看两版固定留出MAE、实际生效版本与历次评估记录；观察席只读，换版仅主管。
3. **拍卖场次和底价**：AuctionSession设开场/截止，AuctionLot关联本批已核级留样和场次。A最低80元/筐、B55元、C30元。挂场先锁Consignment父行，再计算所有未撤场标的占筐。未评级、低底价、超余筐或已截止拒绝。未出价未成交标的可主管撤场释放额度，有出价不得撤场。
4. **竞价与成交锁筐**：Bid须在`opens_at ≤ clock < closes_at`时提交，达到底价并严格高于当前最高价。同父行→场次→业务时钟→标的锁序，避免并发报价检查窗口。主管只能在截止后一次截标，最高价Bid生成唯一Deal；无报价不成交，需撤场。成交冻结买方、单价、筐数与原等级，不能再次出售。
5. **留样争议和复判**：Deal必须已有实际留样天数才可开Dispute，每成交只允许一条未决争议。主管复判不得上调现有效等级，也不得高于冻结终点对应级别（≥10天A、≥7天B、否则C）。复判只追加修订，推进Deal.revision，旧draft结算作废；已付记录保留。
6. **货款结算及差额补退**：A/B/C权重100/90/75，`折后货款=floor(成交筐价×筐数×新等级权重÷原等级权重)`，佣金floor(货款×5%)，目标净款=货款−佣金。本次delta=当前目标−所有已付delta合计；负数为种植户退款。每成交每revision唯一Settlement，争议未决禁止生成/支付，过期/已付/作废拒绝再支付，回单号持久化。金额用整数分。

业务时钟Clock初始2026-11-18 08:00，由主管在“等级挂场”向前推进；场次/截止判定统一用该时钟，无需等待现实时间。界面datetime按本地业务时间解释，不支持时区换算。seed和重启不回拨时钟。

## 真实算法与队列

`backend/src/grading.py`固定NumPy seed35生成200条合成花卉观测：成熟度0.1–1、杆长35–90cm、采后1–40h、冷藏0–25h；目标`clip(14−6×成熟度+.04×(杆长−50)−.13×采后小时+.09×冷藏小时+N(0,.35),2,20)`。先固定拆分150训练/50留出，GradientBoostingRegressor（80树、深度2、seed35）仅拟合训练集，输出留出MAE天数、预测瓶插天数与A/B/C建议。保留源数据SHA256、训练/留出索引与输入快照；不是实际客户农业样本，模型不替代验级员判断。该管线即旧版`v1-synthetic`，其合成留出MAE与重构前完全一致。

新版`v2-sealed`复用同款GradientBoostingRegressor（80树、深度2、seed35），训练数据改为数据库中**已封存实际瓶插终点**的留样（特征为成熟度、杆长、采后小时、冷藏小时，标签为observed_days），按到场批固定留出排除整批后拟合其余批次；在固定留出批上与旧版同口径计算MAE决定是否换版。训练行、留样/批次id与SHA256快照存`model_versions.training_snapshot`，评估结果存`model_evaluations`。模型注册表懒初始化（首次访问`/models`或送估/worker处理时补齐v1/v2两行），`db.ensure_schema()`幂等建新表并给旧库`vase_samples`补`model_version`列。

接口将留样ID送Redis，worker计算真实sklearn结果，DB prediction与`/artifacts/grade-ID.json`共享卷落盘。worker按留样固定的`model_version`取模型并回写实际用版；故障记录failed/error，Redis恢复后可同记录重试，非queued态消息跳过，不重复出结果。未实现worker硬崩溃后的running自动回收，不能声称可靠消息投递。

## 一天的工作剧本

1. 07:30 验级员接`FL031`洋桔梗18筐，每筐40支，采切04:30；核对筐贴FL031-01至18。2筐有历史成交和6天留样争议，剩余16筐可演练。
2. 08:00 对新批建立`FLS-NEW`，成熟度.3、杆长72cm、冷藏2h，送worker估级；查看150/50留出MAE，主管结合验花核定A。
3. 08:10 建`MORNING-NEW`场次08:00–09:00，挂`LOT-NEW`4筐、底价8000分。试7000分挂场被拒，改8000恢复；重复挂超过实收也拒。
4. 08:20 花店甲报价9000分/筐，花店乙10000分；低于底价、同最高价都拒。提前截标拒绝，主管推进业务时钟到09:00后截标，乙成交4筐40000分。
5. 09:10 生成R1货款：40000−2000佣金=38000分，登记`BANK-FIRST`回单。
6. 09:20 买方申请争议，无实际留样终点先被拒。回瓶插页封存6天，再开争议；主管据冻结留样复判C，Deal推进R2。
7. 09:40 R2目标30000货款−1500佣金=28500分；此前已付38000，补退delta为−9500分，登记`REFUND-9500`退款回单。R1保持原值。
8. 10:00 观察席复看成交、留样快照与两次回单；没有外发支付或交易指令，付款/退款是本地业务登记。

## 结构与开发

后端关系实体`models.py`、输入约束`schemas.py`、`auction_service.py`父锁/额度/竞价/成交、`dispute_service.py`证据/修订/金额账、`grading.py`模型、`worker.py`队列、`main.py`逐路由权限。前端六独立pages分别处理arrival/samples/offers/bidding/disputes/settlement，`components/tickets.js`留样等级签/到场签/拍价带等跨页复用；`utils/format.js`类型转义、`utils/actions.js`请求错误恢复、store关联档案。前后端constants均有角色、等级、留样状态、标的状态，后端schema/业务规则执行校验，前端展示实际持久状态。

本地后端安装requirements，配置DATABASE_URL/REDIS_URL/JWT_SECRET，运行`uvicorn src.main:app --reload`与`python -m src.worker`；前端可由Compose Nginx反代/api。seed自然键只补缺：不覆盖人工筐贴、时钟、观察、竞价、争议判定和已付回单。测试与截图在`../../test-artifacts/gb-1035/`。

已知范围：按筐计量，未建单支花追踪/实物退货物流；不接支付网关/买方信用或电子签章；业务时钟人工推进；瓶插终点一次封存后纠错须人工运维，不提供覆盖式修订；合成ML不证明实际寿命；单站父锁会串行化同批交易，适合本题规模。
