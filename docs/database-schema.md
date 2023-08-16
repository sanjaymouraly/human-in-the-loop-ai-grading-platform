# Database Schema

## Overview
SQLite by default, PostgreSQL compatible. All tables use BigAutoField.

## Tables

### accounts_profile
- id, user_id (OneToOne User), role (admin/manager/reviewer/observer), display_name, bio, created_at
- Signal creates profile on User creation

### projects_project
- id, name, description, instructions, task_type (qa/coding/summarization/instruction/reasoning/general), goal, status (draft/active/completed/archived), blind_review bool, require_double_review bool, balance_ab_order bool, created_by_id, created_at, updated_at

### projects_projectmembership
- id, project_id, user_id, role (manager/reviewer/observer), added_at, added_by_id
- unique_together (project, user)

### datasets_dataset
- id, project_id, name, version, description, file_name, row_count, created_by_id, created_at, is_active
- unique_together (project, name, version)

### datasets_datasetitem
- id, dataset_id, project_id, task_id, prompt (text), context (text), response_a (text), response_b (text), model_a (char 100), model_b (char 100), metadata (JSON), reference_answer (text), order_index, content_hash (sha256 for duplicate detection), is_active, created_at
- unique_together (dataset, task_id)
- Index (project, task_id)

### rubrics_rubric
- id, project_id, name, description, version (auto-increment per project), is_active, created_by_id, created_at, instructions
- unique_together (project, version)

### rubrics_rubricdimension
- id, rubric_id, key (slug), name, description, scale_min, scale_max, allow_na, weight (float), anchored_descriptions (JSON), order, is_required
- unique_together (rubric, key)

### evaluations_assignment
- id, project_id, dataset_item_id, reviewer_id, status (pending/in_progress/submitted/skipped), assigned_by_id, assigned_at, due_at, submitted_at, display_a_is_original_a (bool randomized), created_at, updated_at
- unique_together (dataset_item, reviewer)
- Index (project, reviewer, status)

### evaluations_review
- id, assignment_id (OneToOne), project_id, dataset_item_id, reviewer_id, rubric_id (PROTECT), preference (response_a/response_b/tie/both_bad) stored as ORIGINAL label, display_preference (what reviewer clicked), confidence (1-5), rationale (text), is_draft bool, display_a_is_original_a bool (copy for history), time_spent_seconds, submitted_at, created_at, updated_at
- Indexes (project, reviewer), (dataset_item)

### evaluations_reviewdimensionscore
- id, review_id, dimension_id, score_a (int nullable), score_b (int nullable), is_na bool
- unique_together (review, dimension)

### evaluations_issue
- id, review_id, project_id, dataset_item_id, reviewer_id, response_target (response_a/response_b original), category (hallucination, incorrect_calc, unsupported_claim, missed_constraint, formatting, omitted_req, broken_code, reasoning_mistake, unsafe_content, other), severity (low/medium/high/critical), excerpt, evidence, explanation, verification_status (unverified/verified/disputed), correction, created_at

### evaluations_adjudication
- id, project_id, dataset_item_id, adjudicator_id, final_preference, rationale, created_at, reviews_snapshot (JSON list of reviews at adjudication time)
- unique_together (project, dataset_item)

### evaluations_auditlog
- id, project_id (nullable), user_id (nullable), action (char 100), object_type, object_id, details (JSON), timestamp, ip_address

## Relationships
- Project 1--* Dataset, DatasetItem, Rubric, Assignment, Review, Issue, Adjudication, AuditLog, Membership
- Dataset 1--* DatasetItem
- Rubric 1--* RubricDimension, Review
- DatasetItem 1--* Assignment, Review, Issue, Adjudication
- Assignment 1--1 Review
- Review 1--* ReviewDimensionScore, Issue
- User 1--* Profile, ProjectMembership, Assignment, Review, Issue, Adjudication, AuditLog

## Constraints & Integrity
- Unique constraints prevent duplicate assignments and duplicate dimension scores per review
- Rubric versioning via auto-increment, Review PROTECT prevents deletion of used rubrics
- Content hash for duplicate detection (not enforced as unique, but used for warnings)
- Transactions for assignment creation and review submission
- is_active flags for soft deletion/versioning (datasets, items)

## Migrations
- Located in apps/*/migrations/
- Apply via `python manage.py migrate`
- Seed via `python manage.py seed_demo`
