"""
Seed demo data for Human Feedback AI Grader
Creates users, projects, datasets, rubrics, assignments, reviews, disagreements
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
import random
import os

from apps.accounts.models import Profile, Role
from apps.projects.models import Project, ProjectMembership, MembershipRole, TaskType, ProjectStatus
from apps.datasets.models import Dataset, DatasetItem
from apps.rubrics.models import Rubric, RubricDimension
from apps.evaluations.models import Assignment, Review, ReviewDimensionScore, Issue, Adjudication, PreferenceChoice, AssignmentStatus, IssueCategory, IssueSeverity
from apps.rubrics.views import DEFAULT_DIMENSIONS

class Command(BaseCommand):
    help = 'Seed demo data'

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # Get passwords from env or defaults
        admin_pass = os.getenv('DEMO_ADMIN_PASSWORD', 'AdminPass123!')
        manager_pass = os.getenv('DEMO_MANAGER_PASSWORD', 'ManagerPass123!')
        reviewer_pass = os.getenv('DEMO_REVIEWER_PASSWORD', 'ReviewerPass123!')
        observer_pass = os.getenv('DEMO_OBSERVER_PASSWORD', 'ObserverPass123!')

        with transaction.atomic():
            # Create users
            users_data = [
                ('admin', 'admin@example.com', admin_pass, Role.ADMIN, 'Admin User'),
                ('manager', 'manager@example.com', manager_pass, Role.MANAGER, 'Project Manager'),
                ('reviewer1', 'reviewer1@example.com', reviewer_pass, Role.REVIEWER, 'Alice Reviewer'),
                ('reviewer2', 'reviewer2@example.com', reviewer_pass, Role.REVIEWER, 'Bob Reviewer'),
                ('reviewer3', 'reviewer3@example.com', reviewer_pass, Role.REVIEWER, 'Carol Reviewer'),
                ('observer', 'observer@example.com', observer_pass, Role.OBSERVER, 'Observer User'),
            ]

            users = {}
            for username, email, pwd, role, display_name in users_data:
                user, created = User.objects.get_or_create(username=username, defaults={'email': email})
                if created:
                    user.set_password(pwd)
                    user.save()
                    self.stdout.write(f"Created user {username}")
                else:
                    # Update password
                    user.set_password(pwd)
                    user.email = email
                    user.save()
                # Update profile
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.role = role
                profile.display_name = display_name
                profile.save()
                if role == Role.ADMIN:
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                users[username] = user

            # Clear existing demo projects? We'll keep but create new if not exists
            # Create projects
            project_defs = [
                {
                    'name': 'Factual QA Evaluation',
                    'description': 'Evaluate factual accuracy and completeness of QA responses across general knowledge questions.',
                    'instructions': 'Focus on factual correctness. Flag hallucinations with evidence. Prefer accurate, concise answers.',
                    'task_type': TaskType.QA,
                    'goal': 'Measure which model produces fewer hallucinations and more accurate factual answers.',
                    'status': ProjectStatus.ACTIVE,
                    'blind_review': True,
                    'require_double_review': True,
                },
                {
                    'name': 'Code Generation Benchmark',
                    'description': 'Compare code generation quality for Python tasks including correctness, efficiency, and readability.',
                    'instructions': 'Check if code runs, handles edge cases, follows best practices. Report broken code issues.',
                    'task_type': TaskType.CODING,
                    'goal': 'Determine which model generates more correct and maintainable code.',
                    'status': ProjectStatus.ACTIVE,
                    'blind_review': True,
                    'require_double_review': True,
                },
                {
                    'name': 'Summarization Quality',
                    'description': 'Evaluate summarization for coverage, faithfulness, and conciseness.',
                    'instructions': 'Compare summaries against source context. Check for unsupported claims and omission of key points.',
                    'task_type': TaskType.SUMMARIZATION,
                    'goal': 'Assess summarization fidelity and usefulness.',
                    'status': ProjectStatus.ACTIVE,
                    'blind_review': False,
                    'require_double_review': True,
                },
            ]

            projects = []
            for pdef in project_defs:
                proj, created = Project.objects.get_or_create(
                    name=pdef['name'],
                    defaults={
                        'description': pdef['description'],
                        'instructions': pdef['instructions'],
                        'task_type': pdef['task_type'],
                        'goal': pdef['goal'],
                        'status': pdef['status'],
                        'blind_review': pdef['blind_review'],
                        'require_double_review': pdef['require_double_review'],
                        'created_by': users['manager'],
                    }
                )
                if created:
                    self.stdout.write(f"Created project {proj.name}")
                projects.append(proj)

                # Add memberships
                for uname, role in [('manager', MembershipRole.MANAGER), ('reviewer1', MembershipRole.REVIEWER), ('reviewer2', MembershipRole.REVIEWER), ('reviewer3', MembershipRole.REVIEWER), ('observer', MembershipRole.OBSERVER)]:
                    ProjectMembership.objects.get_or_create(
                        project=proj,
                        user=users[uname],
                        defaults={'role': role, 'added_by': users['manager']}
                    )

            # Sample dataset items
            sample_items = [
                # QA
                {
                    'project_idx': 0,
                    'task_id': 'qa_001',
                    'prompt': 'What is the capital of France?',
                    'context': '',
                    'response_a': 'Paris is the capital of France. It is known for its rich history, culture, and landmarks like the Eiffel Tower.',
                    'response_b': 'Lyon is the capital of France, located in the southeast. It is famous for its cuisine and historical architecture.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': 'Paris',
                    'metadata': {'difficulty': 'easy', 'category': 'geography'}
                },
                {
                    'project_idx': 0,
                    'task_id': 'qa_002',
                    'prompt': 'Explain quantum entanglement in simple terms.',
                    'context': '',
                    'response_a': 'Quantum entanglement is when two particles become linked, so measuring one instantly affects the other, even across vast distances. Einstein called it "spooky action at a distance." It does not allow faster-than-light communication.',
                    'response_b': 'Quantum entanglement is when particles are connected and can communicate faster than light, allowing instant messaging across the universe. This is used for quantum internet.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': 'Entangled particles correlated, no FTL communication',
                    'metadata': {'difficulty': 'medium', 'category': 'physics'}
                },
                {
                    'project_idx': 0,
                    'task_id': 'qa_003',
                    'prompt': 'Who wrote Pride and Prejudice and when was it published?',
                    'context': '',
                    'response_a': 'Pride and Prejudice was written by Jane Austen and published in 1813. It is one of her most famous novels.',
                    'response_b': 'Pride and Prejudice was written by Charlotte Brontë in 1847, during the Victorian era.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': 'Jane Austen, 1813',
                    'metadata': {'difficulty': 'easy', 'category': 'literature'}
                },
                # Coding
                {
                    'project_idx': 1,
                    'task_id': 'code_001',
                    'prompt': 'Write a Python function to check if a number is prime.',
                    'context': 'Function should handle edge cases and be efficient.',
                    'response_a': 'def is_prime(n):\n    if n < 2:\n        return False\n    if n == 2:\n        return True\n    if n % 2 == 0:\n        return False\n    for i in range(3, int(n**0.5)+1, 2):\n        if n % i == 0:\n            return False\n    return True',
                    'response_b': 'def is_prime(n):\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True\n# This fails for n<2 and is inefficient',
                    'model_a': 'model-codex',
                    'model_b': 'model-codellama',
                    'reference_answer': '',
                    'metadata': {'language': 'python', 'difficulty': 'easy'}
                },
                {
                    'project_idx': 1,
                    'task_id': 'code_002',
                    'prompt': 'Implement binary search in Python. Return index or -1 if not found.',
                    'context': 'Assume sorted list input.',
                    'response_a': 'def binary_search(arr, target):\n    left, right = 0, len(arr)-1\n    while left <= right:\n        mid = (left+right)//2\n        if arr[mid]==target:\n            return mid\n        elif arr[mid]<target:\n            left=mid+1\n        else:\n            right=mid-1\n    return -1',
                    'response_b': 'def binary_search(arr, target):\n    for i, val in enumerate(arr):\n        if val==target:\n            return i\n    return -1\n# This is linear search, not binary',
                    'model_a': 'model-codex',
                    'model_b': 'model-codellama',
                    'reference_answer': '',
                    'metadata': {'language': 'python', 'difficulty': 'medium'}
                },
                {
                    'project_idx': 1,
                    'task_id': 'code_003',
                    'prompt': 'Write a function to reverse a linked list iteratively.',
                    'context': 'Use standard ListNode definition.',
                    'response_a': 'def reverse_list(head):\n    prev = None\n    curr = head\n    while curr:\n        nxt = curr.next\n        curr.next = prev\n        prev = curr\n        curr = nxt\n    return prev',
                    'response_b': 'def reverse_list(head):\n    # Recursive approach but missing base case\n    return reverse_list(head.next)\n    head.next = None\n',
                    'model_a': 'model-codex',
                    'model_b': 'model-codellama',
                    'reference_answer': '',
                    'metadata': {'language': 'python', 'difficulty': 'medium'}
                },
                # Summarization
                {
                    'project_idx': 2,
                    'task_id': 'summ_001',
                    'prompt': 'Summarize the following article in 2 sentences.',
                    'context': 'Artificial intelligence (AI) has seen rapid growth in recent years, driven by advances in deep learning, increased computational power, and large datasets. Applications range from image recognition to natural language processing. However, challenges remain including bias, interpretability, and energy consumption. Researchers are working on more efficient models and ethical guidelines to ensure responsible deployment.',
                    'response_a': 'AI has grown rapidly due to deep learning, compute, and data, enabling applications like vision and NLP, but faces challenges in bias, interpretability, and energy use, prompting work on efficiency and ethics.',
                    'response_b': 'AI is growing fast and is used for many things. It has some problems but people are fixing them.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': '',
                    'metadata': {'length': 'short', 'source': 'tech'}
                },
                {
                    'project_idx': 2,
                    'task_id': 'summ_002',
                    'prompt': 'Summarize the meeting notes into action items.',
                    'context': 'Meeting notes: John will prepare Q3 report by Friday. Sarah to contact vendor about pricing. Mike to fix login bug (high priority). Team agreed to postpone launch to next month. Budget review scheduled for Monday.',
                    'response_a': 'Action items:\n- John: Q3 report by Friday\n- Sarah: Contact vendor for pricing\n- Mike: Fix high-priority login bug\n- Team: Launch postponed to next month\n- All: Budget review Monday',
                    'response_b': 'John and Sarah have tasks. The launch is postponed. There is a bug to fix.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': '',
                    'metadata': {'type': 'meeting'}
                },
                {
                    'project_idx': 2,
                    'task_id': 'instr_001',
                    'prompt': 'Write a 50-word product description for a wireless earbud, include battery life 20 hours, noise cancellation, and mention color black.',
                    'context': 'Must be exactly marketing tone, 50 words.',
                    'response_a': 'Experience premium sound with our sleek black wireless earbuds. Enjoy 20 hours of battery life and advanced noise cancellation for immersive listening. Perfect for commutes, workouts, and calls. Compact charging case included. Elevate your audio journey with comfort, style, and crystal-clear performance every day.',
                    'response_b': 'These earbuds are great. They have long battery and are black. They sound good and are comfortable.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': '',
                    'metadata': {'task': 'instruction_following'}
                },
                {
                    'project_idx': 2,
                    'task_id': 'reason_001',
                    'prompt': 'If all Bloops are Razzies and some Razzies are Loppies, can we conclude some Bloops are Loppies? Explain.',
                    'context': '',
                    'response_a': 'No, we cannot conclude that. All Bloops are Razzies, but only some Razzies are Loppies. The Bloops could be in the part of Razzies that are not Loppies. So the conclusion does not logically follow. Venn diagram shows overlap not guaranteed.',
                    'response_b': 'Yes, because Bloops are Razzies and some Razzies are Loppies, so some Bloops must be Loppies. This is transitive.',
                    'model_a': 'model-gpt4',
                    'model_b': 'model-claude',
                    'reference_answer': 'No, does not follow',
                    'metadata': {'type': 'reasoning'}
                },
            ]

            # Create datasets
            for proj in projects:
                # Check if dataset exists
                ds_name = f"{proj.name} Demo Dataset"
                existing = Dataset.objects.filter(project=proj, name=ds_name).first()
                if existing:
                    self.stdout.write(f"Dataset {ds_name} already exists, skipping creation")
                    continue

                dataset = Dataset.objects.create(
                    project=proj,
                    name=ds_name,
                    version=1,
                    description=f"Demo dataset for {proj.name}",
                    file_name="demo.json",
                    row_count=0,
                    created_by=users['manager'],
                )

                items = []
                for idx, item_def in enumerate([it for it in sample_items if it['project_idx'] == projects.index(proj)]):
                    items.append(DatasetItem(
                        dataset=dataset,
                        project=proj,
                        task_id=item_def['task_id'],
                        prompt=item_def['prompt'],
                        context=item_def.get('context', ''),
                        response_a=item_def['response_a'],
                        response_b=item_def['response_b'],
                        model_a=item_def.get('model_a', ''),
                        model_b=item_def.get('model_b', ''),
                        metadata=item_def.get('metadata', {}),
                        reference_answer=item_def.get('reference_answer', ''),
                        order_index=idx,
                    ))
                DatasetItem.objects.bulk_create(items)
                dataset.row_count = len(items)
                dataset.save()
                self.stdout.write(f"Created dataset {ds_name} with {len(items)} items")

            # Create rubrics
            for proj in projects:
                if proj.rubrics.exists():
                    self.stdout.write(f"Rubric for {proj.name} already exists")
                    continue
                rubric = Rubric.objects.create(
                    project=proj,
                    name=f"{proj.name} Rubric",
                    description=f"Evaluation rubric for {proj.name}",
                    instructions="Rate each dimension 1-5. 1=Poor, 5=Excellent. Be consistent and provide rationale.",
                    created_by=users['manager'],
                )
                for dim_def in DEFAULT_DIMENSIONS:
                    RubricDimension.objects.create(
                        rubric=rubric,
                        key=dim_def['key'],
                        name=dim_def['name'],
                        description=dim_def.get('description', ''),
                        scale_min=dim_def['scale_min'],
                        scale_max=dim_def['scale_max'],
                        anchored_descriptions=dim_def.get('anchored_descriptions', {}),
                        weight=dim_def.get('weight', 1.0),
                        order=dim_def.get('order', 0)
                    )
                self.stdout.write(f"Created rubric for {proj.name}")

            # Create assignments and reviews
            for proj in projects:
                rubric = proj.rubrics.filter(is_active=True).first()
                if not rubric:
                    continue
                items = proj.dataset_items.filter(is_active=True)[:5]  # first 5 items
                reviewers = [users['reviewer1'], users['reviewer2']]

                for item in items:
                    for reviewer in reviewers:
                        # Assignment
                        assignment, created = Assignment.objects.get_or_create(
                            project=proj,
                            dataset_item=item,
                            reviewer=reviewer,
                            defaults={
                                'assigned_by': users['manager'],
                                'display_a_is_original_a': random.choice([True, False]),
                                'status': AssignmentStatus.SUBMITTED,
                                'submitted_at': timezone.now(),
                            }
                        )
                        if not created:
                            assignment.status = AssignmentStatus.SUBMITTED
                            assignment.submitted_at = timezone.now()
                            assignment.save()

                        # Review - check if exists
                        if hasattr(assignment, 'review') and assignment.review:
                            continue

                        # Determine preference based on item
                        # For demo, make reviewer1 usually correct, reviewer2 sometimes disagrees
                        if 'qa_001' in item.task_id:
                            # A is correct
                            pref = 'response_a' if reviewer.username == 'reviewer1' else random.choice(['response_a', 'response_b'])
                        elif 'qa_002' in item.task_id:
                            pref = 'response_a' if reviewer.username == 'reviewer1' else 'response_b'  # disagreement example
                        elif 'qa_003' in item.task_id:
                            pref = 'response_a'
                        elif 'code_001' in item.task_id:
                            pref = 'response_a'
                        elif 'code_002' in item.task_id:
                            pref = 'response_a' if reviewer.username == 'reviewer1' else 'response_b'
                        else:
                            pref = random.choice(['response_a', 'response_b', 'tie'])

                        # Display preference mapping
                        display_pref = pref
                        if not assignment.display_a_is_original_a:
                            if pref == 'response_a':
                                display_pref = 'response_b'
                            elif pref == 'response_b':
                                display_pref = 'response_a'

                        review = Review.objects.create(
                            assignment=assignment,
                            project=proj,
                            dataset_item=item,
                            reviewer=reviewer,
                            rubric=rubric,
                            preference=pref,
                            display_preference=display_pref,
                            confidence=random.randint(3,5),
                            rationale=f"This is a demo rationale for {item.task_id}. Reviewer {reviewer.username} prefers {pref} because " + ("it is factually correct and complete." if pref=='response_a' else "it seems more concise but may have issues."),
                            is_draft=False,
                            display_a_is_original_a=assignment.display_a_is_original_a,
                            submitted_at=timezone.now(),
                            time_spent_seconds=random.randint(30, 300)
                        )

                        # Dimension scores
                        for dim in rubric.dimensions.all():
                            score_a = random.randint(3,5) if pref in ('response_a', 'tie') else random.randint(1,3)
                            score_b = random.randint(3,5) if pref in ('response_b', 'tie') else random.randint(1,3)
                            # Adjust for known correct
                            if 'qa_001' in item.task_id and dim.key == 'factual_accuracy':
                                score_a, score_b = 5, 1
                            if 'code_001' in item.task_id and dim.key in ('completeness', 'reasoning_quality'):
                                score_a, score_b = 5, 2
                            ReviewDimensionScore.objects.create(
                                review=review,
                                dimension=dim,
                                score_a=score_a,
                                score_b=score_b,
                                is_na=False
                            )

                        # Issues for some reviews
                        if 'qa_001' in item.task_id and pref == 'response_a':
                            # Report issue on B
                            Issue.objects.create(
                                review=review,
                                project=proj,
                                dataset_item=item,
                                reviewer=reviewer,
                                response_target='response_b',
                                category=IssueCategory.HALLUCINATION,
                                severity=IssueSeverity.HIGH,
                                excerpt='Lyon is the capital of France',
                                evidence='Paris is capital per reference',
                                explanation='Hallucinated capital city',
                                verification_status='verified',
                                correction='Paris is the capital of France'
                            )
                        if 'code_002' in item.task_id:
                            Issue.objects.create(
                                review=review,
                                project=proj,
                                dataset_item=item,
                                reviewer=reviewer,
                                response_target='response_b',
                                category=IssueCategory.BROKEN_CODE,
                                severity=IssueSeverity.HIGH,
                                excerpt='for i, val in enumerate(arr):',
                                explanation='Implements linear search instead of binary search as requested',
                                evidence='Prompt asks for binary search O(log n), not O(n)',
                            )

                self.stdout.write(f"Created assignments/reviews for {proj.name}")

            # Create adjudications for disagreements
            for proj in projects:
                # Find items with disagreement
                from django.db.models import Count
                items_with_disagreement = []
                for item in proj.dataset_items.filter(is_active=True):
                    revs = item.reviews.filter(is_draft=False)
                    if revs.count() >= 2:
                        prefs = set(revs.values_list('preference', flat=True))
                        if len(prefs) > 1 and not item.adjudications.exists():
                            items_with_disagreement.append(item)

                for item in items_with_disagreement[:2]:  # adjudicate first 2
                    reviews = item.reviews.filter(is_draft=False)
                    snapshot = []
                    for r in reviews:
                        snapshot.append({
                            'reviewer': r.reviewer.username,
                            'preference': r.preference,
                            'confidence': r.confidence,
                            'rationale': r.rationale,
                        })
                    # Final preference: choose majority or correct one
                    # For demo, pick response_a as final for QA items
                    final_pref = 'response_a' if 'qa' in item.task_id or 'code' in item.task_id else 'tie'
                    Adjudication.objects.create(
                        project=proj,
                        dataset_item=item,
                        adjudicator=users['manager'],
                        final_preference=final_pref,
                        rationale=f"After reviewing both independent evaluations, final decision is {final_pref}. Evidence shows response A is factually correct while B contains errors. Original judgments preserved.",
                        reviews_snapshot=snapshot
                    )
                self.stdout.write(f"Created adjudications for {proj.name}")

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write("Users: admin, manager, reviewer1, reviewer2, reviewer3, observer")
        self.stdout.write("Passwords from env or defaults: AdminPass123!, ManagerPass123!, ReviewerPass123!, ObserverPass123!")
