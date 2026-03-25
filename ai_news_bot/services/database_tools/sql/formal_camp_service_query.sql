-- 目的：找出"训练营 > 正式营"中，关联"产研测试"品类且未配置"售后接待"的课程
-- 目标表：ql_financial_camp (f), ql_category (cat)

SELECT 
    f.id_ AS 营期ID,
    f.name_ AS 营期名称,
    cat.name_ AS 所属品类,
    f.finacial_type_ AS 财务类型,
    f.is_assign_sale_after_ AS 是否售后接待,
    f.reception_group_id_ AS 接待组ID
FROM ql_financial_camp f
LEFT JOIN ql_category cat ON f.category_id_ = cat.id_
WHERE 
    f.status_ = 'Y' -- 有效状态
    AND f.finacial_type_ = 'FORMAL' -- 业务类型为正式营
    AND cat.name_ = '产研测试' -- 锁定“产研测试”品类
    AND (f.is_assign_sale_after_ = 'N' OR f.is_assign_sale_after_ IS NULL) -- 售后配置为“否”
ORDER BY f.create_time_ DESC;
