# Implementation Plan: OpenBoard Forum

## Overview

实现类似贴吧的学习社区功能，包括论坛管理、发帖回复、搜索、老师管理等功能。采用 Next.js 前端 + FastAPI 后端 + PostgreSQL 数据库。

## Tasks

- [x] 1. 数据库表创建
  - 创建 forums, forum_posts, forum_replies, forum_mod_logs, forum_user_status 表
  - 添加必要的索引
  - _Requirements: 1.1-1.5, 2.1-2.5, 3.1-3.3, 5.1-5.2, 6.1-6.5, 7.1-7.2_

- [x] 2. 后端 API 实现
  - [x] 2.1 创建 OpenBoard 路由模块
    - 创建 `src/api/routes/openboard.py`
    - 定义 Pydantic 模型
    - _Requirements: All_

  - [x] 2.2 实现论坛管理 API
    - GET /api/openboard/forums - 获取论坛列表
    - POST /api/openboard/forums - 创建论坛申请
    - POST /api/openboard/forums/{id}/approve - 审核论坛
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.3 实现帖子管理 API
    - GET /api/openboard/forums/{id}/posts - 获取帖子列表
    - POST /api/openboard/posts - 创建帖子
    - GET /api/openboard/posts/{id} - 获取帖子详情
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [x] 2.4 实现回复 API
    - POST /api/openboard/posts/{id}/replies - 添加回复
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.5 实现搜索 API
    - GET /api/openboard/search - 搜索帖子
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 2.6 实现管理员 API
    - DELETE /api/openboard/admin/posts/{id} - 删除帖子
    - POST /api/openboard/admin/ban - 封禁/解封用户
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3. Checkpoint - 后端 API 测试
  - 确保所有 API 端点可用
  - 使用 curl 或 Postman 测试

- [x] 4. 前端页面实现
  - [x] 4.1 创建论坛列表页面
    - 路由: `/student/openboard/page.tsx`
    - 显示论坛卡片列表
    - 创建论坛申请按钮
    - _Requirements: 1.4, 1.5, 7.1, 7.2_

  - [x] 4.2 创建论坛详情页面
    - 路由: `/student/openboard/[forumId]/page.tsx`
    - 显示帖子列表
    - 发帖按钮和表单
    - _Requirements: 2.4, 7.1, 7.2, 7.3_

  - [x] 4.3 创建帖子详情页面
    - 路由: `/student/openboard/post/[postId]/page.tsx`
    - 显示帖子内容和回复
    - 回复表单
    - _Requirements: 2.5, 3.2, 3.3_

  - [x] 4.4 创建搜索页面
    - 路由: `/student/openboard/search/page.tsx`
    - 搜索框和结果列表
    - 论坛筛选下拉框
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 4.5 创建老师管理面板
    - 路由: `/teacher/openboard/page.tsx`
    - 待审核论坛列表
    - 用户管理（封禁/解封）
    - 帖子删除功能
    - _Requirements: 1.2, 1.3, 5.1, 5.3, 6.1, 6.3, 6.4_

- [x] 5. 前端 API 服务
  - [x] 5.1 创建 openboardApi 服务
    - 在 `services/api.ts` 中添加 OpenBoard API 调用
    - _Requirements: All_

- [x] 6. Checkpoint - 前端功能测试
  - 确保所有页面正常渲染
  - 测试完整用户流程

- [x] 7. 集成测试
  - [x] 7.1 测试完整流程
    - 创建论坛 → 审核 → 发帖 → 回复 → 搜索
    - _Requirements: All_

  - [x] 7.2 测试管理功能
    - 删帖、封禁、解封
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_

- [x] 8. Property-Based Tests
  - [x] 8.1 Write property test for forum status transitions
    - **Property 1: Forum Status Transitions**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 8.2 Write property test for reply count consistency
    - **Property 3: Reply Count Consistency**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x] 8.3 Write property test for search relevance
    - **Property 4: Search Result Relevance**
    - **Validates: Requirements 4.1, 4.2, 4.3**

- [x] 9. Final Checkpoint
  - 确保所有功能正常工作
  - 确保老师管理权限正确

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
