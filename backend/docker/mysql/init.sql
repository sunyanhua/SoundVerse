-- SoundVerse MySQL数据库初始化脚本
-- 创建于: 2026-03-06

-- 设置字符集和排序规则
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET COLLATION_CONNECTION = 'utf8mb4_unicode_ci';

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS soundverse
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 使用soundverse数据库
USE soundverse;

-- 创建用户并授予权限（用户已在docker-compose中创建，这里只需要授权）
GRANT ALL PRIVILEGES ON soundverse.* TO 'soundverse'@'%';
FLUSH PRIVILEGES;

-- 注意：表结构将通过Alembic迁移自动创建
-- 此脚本仅确保数据库和用户权限正确设置