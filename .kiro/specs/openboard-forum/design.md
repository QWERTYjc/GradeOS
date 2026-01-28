# Design Document: OpenBoard Forum

## Overview

OpenBoard 是一个学习社区论坛系统，采用类似贴吧的设计。系统分为前端（Next.js）和后端（FastAPI + PostgreSQL），支持主题吧创建审核、发帖回复、搜索、以及老师管理功能。

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Forum   │  │ Post    │  │ Search  │  │ Admin   │        │
│  │ List    │  │ Detail  │  │ Page    │  │ Panel   │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
└───────┼────────────┼────────────┼────────────┼──────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              /api/openboard/*                        │    │
│  │  - /forums (GET, POST)                              │    │
│  │  - /forums/{id}/approve (POST)                      │    │
│  │  - /posts (GET, POST)                               │    │
│  │  - /posts/{id}/replies (GET, POST)                  │    │
│  │  - /search (GET)                                    │    │
│  │  - /admin/ban (POST), /admin/delete (DELETE)        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ forums   │  │ posts    │  │ replies  │  │ mod_logs │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### Backend API Endpoints

#### Forum Management
```python
# 获取论坛列表
GET /api/openboard/forums
Response: List[ForumResponse]

# 创建论坛申请
POST /api/openboard/forums
Body: { name: str, description: str, creator_id: str }
Response: ForumResponse

# 审核论坛（老师）
POST /api/openboard/forums/{forum_id}/approve
Body: { approved: bool, reason?: str }
Response: ForumResponse
```

#### Post Management
```python
# 获取帖子列表
GET /api/openboard/forums/{forum_id}/posts
Query: page, limit
Response: List[PostResponse]

# 创建帖子
POST /api/openboard/posts
Body: { forum_id: str, title: str, content: str, author_id: str }
Response: PostResponse

# 获取帖子详情
GET /api/openboard/posts/{post_id}
Response: PostDetailResponse (includes replies)
```

#### Reply Management
```python
# 添加回复
POST /api/openboard/posts/{post_id}/replies
Body: { content: str, author_id: str }
Response: ReplyResponse
```

#### Search
```python
# 搜索帖子
GET /api/openboard/search
Query: q (keyword), forum_id? (optional filter)
Response: List[SearchResultResponse]
```

#### Admin (Teacher Only)
```python
# 删除帖子
DELETE /api/openboard/admin/posts/{post_id}
Body: { moderator_id: str }
Response: { success: bool }

# 封禁用户
POST /api/openboard/admin/ban
Body: { user_id: str, moderator_id: str, banned: bool }
Response: { success: bool }
```

### Frontend Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/student/openboard` | ForumList | 论坛列表页 |
| `/student/openboard/[forumId]` | ForumDetail | 论坛详情（帖子列表） |
| `/student/openboard/post/[postId]` | PostDetail | 帖子详情（含回复） |
| `/student/openboard/search` | SearchPage | 搜索页面 |
| `/teacher/openboard/admin` | AdminPanel | 管理面板 |

## Data Models

### Database Tables

```sql
-- 论坛表
CREATE TABLE forums (
    forum_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    creator_id VARCHAR(50) REFERENCES users(user_id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'rejected')),
    rejection_reason TEXT,
    post_count INTEGER DEFAULT 0,
    last_activity_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 帖子表
CREATE TABLE forum_posts (
    post_id VARCHAR(100) PRIMARY KEY,
    forum_id VARCHAR(100) REFERENCES forums(forum_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    author_id VARCHAR(50) REFERENCES users(user_id),
    reply_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 回复表
CREATE TABLE forum_replies (
    reply_id VARCHAR(100) PRIMARY KEY,
    post_id VARCHAR(100) REFERENCES forum_posts(post_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_id VARCHAR(50) REFERENCES users(user_id),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 管理日志表
CREATE TABLE forum_mod_logs (
    log_id VARCHAR(100) PRIMARY KEY,
    moderator_id VARCHAR(50) REFERENCES users(user_id),
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_id VARCHAR(100) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 用户论坛状态表（封禁状态）
CREATE TABLE forum_user_status (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    is_banned BOOLEAN DEFAULT FALSE,
    banned_at TIMESTAMP,
    banned_by VARCHAR(50) REFERENCES users(user_id),
    ban_reason TEXT,
    UNIQUE(user_id)
);
```

### TypeScript Types

```typescript
interface Forum {
  forum_id: string;
  name: string;
  description: string;
  creator_id: string;
  creator_name?: string;
  status: 'pending' | 'active' | 'rejected';
  post_count: number;
  last_activity_at?: string;
  created_at: string;
}

interface Post {
  post_id: string;
  forum_id: string;
  forum_name?: string;
  title: string;
  content: string;
  author_id: string;
  author_name?: string;
  reply_count: number;
  created_at: string;
}

interface Reply {
  reply_id: string;
  post_id: string;
  content: string;
  author_id: string;
  author_name?: string;
  created_at: string;
}

interface SearchResult {
  post_id: string;
  title: string;
  content_snippet: string;
  forum_id: string;
  forum_name: string;
  author_name: string;
  created_at: string;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do.*

### Property 1: Forum Status Transitions
*For any* forum creation request, the initial status SHALL be 'pending', and only teacher approval/rejection SHALL change the status to 'active' or 'rejected'.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Post CRUD with Metadata
*For any* post created with valid title and content, the system SHALL persist the post with correct author_id, forum_id, timestamp, and the post SHALL appear in the forum's post list.
**Validates: Requirements 2.1, 2.2, 2.4, 2.5**

### Property 3: Reply Count Consistency
*For any* reply added to a post, the post's reply_count SHALL increment by exactly 1, and replies SHALL be returned in chronological order.
**Validates: Requirements 3.1, 3.2, 3.3**

### Property 4: Search Result Relevance
*For any* search query, all returned posts SHALL contain the search keyword in either title or content, and when filtered by forum_id, all results SHALL belong to that forum.
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 5: Post Deletion with Cascade
*For any* post deleted by a teacher, the post and all its replies SHALL be removed (or marked deleted), and an audit log entry SHALL be created with moderator_id and timestamp.
**Validates: Requirements 5.1, 5.2**

### Property 6: User Ban/Unban Cycle
*For any* user banned by a teacher, the user's posting attempts SHALL fail with an error. After unbanning, the user SHALL be able to post again.
**Validates: Requirements 6.1, 6.2, 6.3**

### Property 7: Forum Statistics Accuracy
*For any* forum, the displayed post_count SHALL equal the actual number of non-deleted posts, and last_activity_at SHALL reflect the most recent post or reply time.
**Validates: Requirements 7.1, 7.2**

## Error Handling

| Error Case | Response | HTTP Code |
|------------|----------|-----------|
| Forum not found | `{"error": "Forum not found"}` | 404 |
| Post not found | `{"error": "Post not found"}` | 404 |
| User is banned | `{"error": "您已被禁言，无法发帖"}` | 403 |
| Not authorized (non-teacher) | `{"error": "权限不足"}` | 403 |
| Invalid forum status | `{"error": "论坛未通过审核"}` | 400 |
| Empty content | `{"error": "内容不能为空"}` | 400 |

## Testing Strategy

### Unit Tests
- Forum CRUD operations
- Post CRUD operations
- Reply CRUD operations
- Search functionality
- Authorization checks

### Property-Based Tests
- Use Hypothesis (Python) for backend property tests
- Minimum 100 iterations per property
- Test data generators for Forum, Post, Reply objects

### Integration Tests
- Full workflow: create forum → approve → create post → reply → search
- Ban/unban workflow
- Delete cascade verification
