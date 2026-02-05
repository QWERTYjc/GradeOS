# Requirements Document

## Introduction

OpenBoard 是一个类似贴吧的学习社区功能，允许学生在老师审核下创建主题吧（如"数学好题分享吧"、"经济笔记分享吧"），学生可以在吧内发帖、回复、搜索，老师拥有管理权限（封号、删帖）。

## Glossary

- **Forum**: 主题吧，一个特定主题的讨论区域
- **Post**: 帖子，用户发布的内容
- **Reply**: 回复，对帖子的评论
- **Moderator**: 版主，拥有管理权限的老师
- **User_Status**: 用户状态（active/banned）

## Requirements

### Requirement 1: Forum Management

**User Story:** As a student, I want to create topic forums with teacher approval, so that I can organize discussions by subject.

#### Acceptance Criteria

1. WHEN a student submits a forum creation request, THE System SHALL create a pending forum awaiting teacher approval
2. WHEN a teacher approves a forum request, THE System SHALL activate the forum and notify the creator
3. WHEN a teacher rejects a forum request, THE System SHALL notify the creator with rejection reason
4. THE System SHALL display forum name, description, creator, and post count on the forum list
5. WHEN a user visits the forum list, THE System SHALL show forums sorted by activity (most recent posts first)

### Requirement 2: Post Creation and Display

**User Story:** As a student, I want to create posts in forums, so that I can share knowledge and ask questions.

#### Acceptance Criteria

1. WHEN a user creates a post with title and content, THE System SHALL save the post and display it in the forum
2. WHEN a post is created, THE System SHALL record author, timestamp, and forum association
3. THE System SHALL support rich text content including text and images
4. WHEN displaying posts, THE System SHALL show title, author, creation time, and reply count
5. WHEN a user views a post, THE System SHALL display full content and all replies

### Requirement 3: Reply System

**User Story:** As a student, I want to reply to posts, so that I can participate in discussions.

#### Acceptance Criteria

1. WHEN a user submits a reply to a post, THE System SHALL save the reply and update the post's reply count
2. WHEN displaying replies, THE System SHALL show author, timestamp, and content
3. THE System SHALL display replies in chronological order (oldest first)

### Requirement 4: Search Functionality

**User Story:** As a user, I want to search posts by keywords, so that I can find relevant content quickly.

#### Acceptance Criteria

1. WHEN a user searches with keywords, THE System SHALL return posts matching title or content
2. WHEN displaying search results, THE System SHALL show post title, forum name, author, and snippet
3. THE System SHALL support filtering search results by forum
4. IF no results are found, THEN THE System SHALL display a friendly message

### Requirement 5: Teacher Moderation - Post Management

**User Story:** As a teacher, I want to delete inappropriate posts, so that I can maintain community quality.

#### Acceptance Criteria

1. WHEN a teacher deletes a post, THE System SHALL remove the post and all its replies
2. WHEN a post is deleted, THE System SHALL log the action with moderator ID and timestamp
3. THE System SHALL display a delete button only to teachers on each post

### Requirement 6: Teacher Moderation - User Management

**User Story:** As a teacher, I want to ban users who violate rules, so that I can protect the community.

#### Acceptance Criteria

1. WHEN a teacher bans a user, THE System SHALL set user status to banned and prevent posting
2. WHEN a banned user attempts to post, THE System SHALL display a ban notification
3. WHEN a teacher unbans a user, THE System SHALL restore posting privileges
4. THE System SHALL display ban/unban controls only to teachers on user profiles
5. WHEN viewing user profile, THE System SHALL show user's post history and current status

### Requirement 7: Forum Statistics

**User Story:** As a user, I want to see forum activity statistics, so that I can find active communities.

#### Acceptance Criteria

1. THE System SHALL display total posts and total replies for each forum
2. THE System SHALL show the most recent post time for each forum
3. WHEN a forum has no posts, THE System SHALL display "暂无帖子"
