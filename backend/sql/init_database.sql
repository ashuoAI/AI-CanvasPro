-- ============================================================
-- AI CanvasPro 数据库初始化脚本
-- 目标数据库: design_team_db (与设计管理系统共享)
-- MySQL 版本: 8.0+
-- ============================================================

-- 创建数据库（如不存在）
CREATE DATABASE IF NOT EXISTS design_team_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE design_team_db;

-- ============================================================
-- 1. 用户表（与设计管理系统共享）
--    字段对齐设计管理系统 auth.js / users.js 中的用户模型
--    - 注册字段: username, email, password, realName, position, dailyCost
--    - 角色: admin / manager / designer / pm
--    - 状态: active / inactive
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    username                VARCHAR(50)     NOT NULL,
    email                   VARCHAR(128)    NOT NULL,
    password                VARCHAR(255)    NOT NULL            COMMENT 'bcrypt 哈希密码',
    real_name               VARCHAR(50)     NOT NULL            COMMENT '真实姓名',
    position                VARCHAR(50)     NOT NULL            COMMENT '职位',
    role                    VARCHAR(32)     NOT NULL DEFAULT 'designer' COMMENT '角色: admin/manager/designer/pm',
    daily_cost              DECIMAL(10,2)   DEFAULT 0.00       COMMENT '日成本',
    phone                   VARCHAR(20)     DEFAULT NULL        COMMENT '手机号码',
    design_level_coefficient DECIMAL(4,2)   DEFAULT 1.00       COMMENT '设计水平系数 0.50-2.00',
    avatar                  VARCHAR(512)    DEFAULT NULL        COMMENT '头像URL',
    status                  VARCHAR(16)     NOT NULL DEFAULT 'active' COMMENT '状态: active=正常 inactive=禁用',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_email (email),
    KEY idx_role (role),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表 - 与设计管理系统共享';

-- ============================================================
-- 2. 用户令牌表（用于跨系统无缝跳转认证）
--    设计管理系统登录后生成 token，用户携带 token 跳转到本程序
-- ============================================================
CREATE TABLE IF NOT EXISTS user_auth_tokens (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,
    token           VARCHAR(256)    NOT NULL,
    token_type      VARCHAR(32)     NOT NULL DEFAULT 'api'       COMMENT 'token类型: api=API令牌 jwt=JWT令牌',
    expires_at      DATETIME        NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_token (token),
    KEY idx_user_id (user_id),
    KEY idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户认证令牌表 - 用于设计管理系统与本程序间的无缝跳转';

-- ============================================================
-- 3. 个人项目数据表
--    存储用户在 AI CanvasPro 中创建的项目数据
-- ============================================================
CREATE TABLE IF NOT EXISTS personal_projects (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    project_id      VARCHAR(64)     NOT NULL            COMMENT '项目唯一标识符(UUID)',
    user_id         INT UNSIGNED    NOT NULL            COMMENT '所属用户ID，关联设计管理系统用户表',
    project_name    VARCHAR(255)    NOT NULL            COMMENT '项目名称',
    project_description TEXT        DEFAULT NULL        COMMENT '项目描述',
    thumbnail       VARCHAR(512)    DEFAULT NULL        COMMENT '项目缩略图路径',
    project_data    JSON            DEFAULT NULL        COMMENT '项目完整数据(画布节点、连线等JSON)',
    project_status  VARCHAR(32)     NOT NULL DEFAULT 'draft' COMMENT '项目状态: draft=草稿 active=活跃 archived=已归档 deleted=已删除',
    canvas_name     VARCHAR(128)    DEFAULT NULL        COMMENT '关联的画布名称',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_id (project_id),
    KEY idx_user_id (user_id),
    KEY idx_user_status (user_id, project_status),
    KEY idx_updated_at (updated_at),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='个人项目数据表 - 存储用户的项目相关数据';

-- ============================================================
-- 4. 个人设置数据表
--    存储用户的个性化设置（不包含 API Key、文件与保存、订阅中心）
--    包含：外观设置、画布偏好、节点行为、快捷键、语言等
-- ============================================================
CREATE TABLE IF NOT EXISTS personal_settings (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL            COMMENT '所属用户ID，关联设计管理系统用户表',
    theme           VARCHAR(32)     NOT NULL DEFAULT 'auto' COMMENT '主题: light=浅色 dark=深色 auto=自动',
    language        VARCHAR(16)     NOT NULL DEFAULT 'zh-CN' COMMENT '界面语言',
    canvas_preferences JSON        DEFAULT NULL         COMMENT '画布偏好设置(网格、对齐、缩放等)',
    node_behavior   JSON            DEFAULT NULL         COMMENT '节点行为设置(默认尺寸、自动保存等)',
    appearance      JSON            DEFAULT NULL         COMMENT '外观设置(字体大小、间距等)',
    notification    JSON            DEFAULT NULL         COMMENT '通知偏好设置',
    shortcuts       JSON            DEFAULT NULL         COMMENT '自定义快捷键设置',
    other_settings  JSON            DEFAULT NULL         COMMENT '其他个性化设置(扩展字段)',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_id (user_id),
    KEY idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='个人设置数据表 - 存储用户的个性化设置（不含API Key/文件保存/订阅）';

-- ============================================================
-- 5. 项目协作表（可选扩展）
--    支持多人协作同一个项目
-- ============================================================
CREATE TABLE IF NOT EXISTS project_collaborators (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    project_id      VARCHAR(64)     NOT NULL            COMMENT '项目ID',
    user_id         INT UNSIGNED    NOT NULL            COMMENT '协作者用户ID',
    permission      VARCHAR(32)     NOT NULL DEFAULT 'view' COMMENT '权限: view=查看 edit=编辑 admin=管理',
    invited_by      INT UNSIGNED    DEFAULT NULL        COMMENT '邀请人用户ID',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_user (project_id, user_id),
    KEY idx_user_id (user_id),
    KEY idx_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='项目协作者表 - 支持多人协作';