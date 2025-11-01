# Linear Operations Priority for AI Agent Testing

## Tier 1: Essential Operations (Must Test)

### Read Operations (Queries)
1. **`viewer`** - Get current authenticated user info
2. **`issues`** - List/filter issues (with filters for team, assignee, state, priority)
3. **`issue`** - Get specific issue by ID
4. **`teams`** - List all teams
5. **`team`** - Get specific team details
6. **`workflowStates`** - Get workflow states for a team (Todo, In Progress, Done, etc.)
7. **`users`** - List users in organization
8. **`organization`** - Get organization details

### Write Operations (Mutations)
1. **`issueCreate`** - Create new issue
2. **`issueUpdate`** - Update issue (title, description, priority, assignee, state)
3. **`commentCreate`** - Add comment to issue

## Tier 2: Common Operations (Should Test)

### Read Operations
9. **`user`** - Get specific user details
10. **`searchIssues`** - Full-text search across issues
11. **`projects`** - List projects
12. **`cycles`** - List cycles/sprints
13. **`issueRelations`** - Get related issues

### Write Operations
4. **`issueArchive`** - Archive completed/cancelled issues
5. **`teamCreate`** - Create new team
6. **`issueBatchCreate`** - Create multiple issues at once
7. **`issueAddLabel`** - Add label to issue
8. **`issueRemoveLabel`** - Remove label from issue

## Tier 3: Advanced Operations (Nice to Have)

### Read Operations
14. **`issueSearch`** - Alternative search implementation
15. **`attachments`** - List attachments
16. **`notifications`** - Get user notifications
17. **`documents`** - List documents

### Write Operations
9. **`projectCreate`** - Create new project
10. **`projectUpdate`** - Update project details
11. **`issueRelationCreate`** - Link related issues (blocks, duplicates, relates to)
12. **`issueLabelCreate`** - Create new label
13. **`attachmentCreate`** - Add attachment/link to issue
14. **`cycleCreate`** - Create new cycle/sprint
15. **`commentUpdate`** - Update existing comment
16. **`commentDelete`** - Delete comment
17. **`issueUnarchive`** - Restore archived issue
18. **`issueDelete`** - Delete issue permanently
19. **`teamUpdate`** - Update team settings
20. **`workflowStateCreate`** - Create custom workflow state

## Current Test Coverage (linear_bench.json)

Covered in test suite:
- ✅ issueCreate (test_1, test_7)
- ✅ issueUpdate - status (test_2)
- ✅ issueUpdate - assignee (test_3)
- ✅ issueUpdate - priority (test_6)
- ✅ issueUpdate - description (test_8)
- ✅ issueUpdate - complete (test_10)
- ✅ commentCreate (test_4)
- ✅ teamCreate (test_5)
- ✅ issueBatchCreate (test_9)

## Gaps to Fill

### High Priority Missing:
- viewer query
- issues list/filter query
- issue get by ID query
- teams list query
- team get by ID query
- workflowStates query
- users list query
- organization query
- issueArchive mutation

### Medium Priority Missing:
- searchIssues query
- issueAddLabel / issueRemoveLabel mutations
- projects query
- projectCreate mutation
- issueRelationCreate mutation
- cycles query

## Testing Strategy

### Phase 1: Core CRUD (Tier 1)
Focus on basic read/write operations that every AI agent will use:
- Query viewer, issues, teams, workflowStates
- Mutations: issueCreate, issueUpdate, commentCreate

### Phase 2: Search & Organization (Tier 2)
Add search, labels, and batch operations:
- searchIssues query
- issueAddLabel/removeLabel mutations
- issueBatchCreate mutation
- issueArchive mutation

### Phase 3: Advanced Features (Tier 3)
Projects, cycles, relations, and admin operations:
- Project management (create, update, list)
- Cycle/sprint management
- Issue relations and linking
- Attachments and documents

## Code Executor Testing Priority

Test with both Python and TypeScript/Bash executors:

1. **Simple query** - viewer
2. **Filtered query** - issues with team filter
3. **Simple mutation** - issueCreate
4. **Complex mutation** - issueUpdate with multiple fields
5. **Search operation** - searchIssues with text query
6. **Batch operation** - issueBatchCreate
7. **Relational operation** - issueRelationCreate