-- =============================================
-- 脚本说明：为首页每个分类随机关联50个课程
-- 运行环境：MySQL 5.7+
-- 注意事项：
-- 1. 假设 ql_tv_home_category (分类表) 和 ql_tv_course (课程表) 已有数据
-- 2. 使用 UUID_SHORT() 生成BIGINT类型的唯一主键ID
-- =============================================

DROP PROCEDURE IF EXISTS `proc_init_category_courses`;

DELIMITER ;;

CREATE PROCEDURE `proc_init_category_courses`()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_category_id BIGINT;
    DECLARE v_count INT DEFAULT 0;
    
    -- 1. 声明游标：获取所有启用且未删除的分类
    DECLARE cur_category CURSOR FOR 
        SELECT id_ FROM ql_tv_home_category WHERE enabled_ = 1 AND deleted_ = 0;
        
    -- 定义游标结束的处理句柄
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    -- 打开游标
    OPEN cur_category;

    read_loop: LOOP
        FETCH cur_category INTO v_category_id;
        
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- 2. 为当前分类执行插入操作
        -- 逻辑：从课程表中随机选取50个未删除的课程，插入到关联表
        INSERT IGNORE INTO ql_tv_home_category_course (
            id_, 
            category_id_, 
            course_id_, 
            sort_, 
            create_by_,
            create_time_, 
            update_by_,
            update_time_,
            deleted_
        )
        SELECT 
            UUID_SHORT(),           -- 生成唯一ID (如需严格雪花算法，建议由Python/Java代码处理)
            v_category_id,          -- 当前循环到的分类ID
            c.id_,                  -- 选中的课程ID
            FLOOR(RAND() * 1000),   -- 随机排序权重
            4209891483,             -- 创建人ID (林康保)
            NOW(),                  -- 创建时间
            4209891483,             -- 更新人ID (林康保)
            NOW(),                  -- 更新时间
            0                       -- 未删除
        FROM ql_tv_course c
        WHERE c.enabled_ = 1 AND c.deleted_ = 0
        AND NOT EXISTS (
            -- 排除该分类下已经存在的课程，避免重复 (虽然Insert Ignore也能处理，但这样更严谨)
            SELECT 1 FROM ql_tv_home_category_course A 
            WHERE A.category_id_ = v_category_id AND A.course_id_ = c.id_
            AND A.deleted_ = 0
        )
        ORDER BY RAND()             -- 随机排序
        LIMIT 50;                   -- 限制50条
        
        SET v_count = v_count + ROW_COUNT();
        
    END LOOP;

    -- 关闭游标
    CLOSE cur_category;
    
    SELECT CONCAT('执行完成：共插入关联数据 ', v_count, ' 条') AS execution_result;
END;;

DELIMITER ;

-- 3. 执行存储过程
CALL `proc_init_category_courses`();

-- 4. 清理存储过程
DROP PROCEDURE IF EXISTS `proc_init_category_courses`;
