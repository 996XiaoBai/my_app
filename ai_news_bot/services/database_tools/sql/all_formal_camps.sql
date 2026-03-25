-- 目的：获取所有"训练营 > 正式营"的有效课程清单
-- 关联品类表以显示业务分类

SELECT 
    f.id_ AS 营期ID,
    f.name_ AS 营期名称,
    cat.name_ AS 所属品类,
    f.price_ / 100 AS 原价_元,
    f.best_price_ / 100 AS 优惠价_元,
    f.is_assign_sale_after_ AS 是否开启售后接待,
    f.create_time_ AS 创建日期
FROM ql_financial_camp f
LEFT JOIN ql_category cat ON f.category_id_ = cat.id_
WHERE 
    f.status_ = 'Y' -- 仅查询有效的数据
    AND f.finacial_type_ = 'FORMAL' -- 筛选正式营
ORDER BY f.create_time_ DESC;
