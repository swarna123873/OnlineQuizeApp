import json
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from accounts.permissions import student_required, educator_required, IsEducatorUser, IsStudentUser
from academics.models import SchoolAcademicContext, CollegeAcademicContext
from content.models import UploadedDocument, QuestionDraft
from .models import Assessment, AssessmentQuestion, AssessmentAttempt, StudentResponse, IntegrityEvent
from psychometrics.ability_estimation import AbilityEstimator
from psychometrics.irt_model import calculate_item_information
from .adaptive_engine import AdaptiveEngine
from ml.prediction_service import get_prediction_service

@student_required
def student_dashboard_view(request):
    attempts = AssessmentAttempt.objects.filter(
        student=request.user
    ).select_related('assessment').prefetch_related('responses').order_by('-started_at')

    completed_attempts = [a for a in attempts if a.status == 'completed']
    total_completed = len(completed_attempts)
    avg_accuracy = round(sum(a.accuracy or 0 for a in completed_attempts) / total_completed, 1) if total_completed > 0 else 0
    latest_theta = completed_attempts[0].final_theta if total_completed > 0 else None

    context = {
        'attempts': attempts,
        'total_completed': total_completed,
        'avg_accuracy': avg_accuracy,
        'latest_theta': latest_theta,
    }
    return render(request, 'student_dashboard.html', context)

@student_required
def student_school_zone_view(request):
    return render(request, 'school_zone.html')

@student_required
def student_college_zone_view(request):
    return render(request, 'college_zone.html')


# REST API Endpoints
class PublishAssessmentAPIView(APIView):
    """
    Publishes an assessment from approved question drafts.
    Requires at least 10 approved questions for psychometric validity.
    """
    permission_classes = [IsEducatorUser]

    def post(self, request):
        doc_id = request.data.get('document_id')
        academic_type = request.data.get('academic_type', '').strip().lower()
        academic_id = request.data.get('academic_id')

        doc = get_object_or_404(UploadedDocument, id=doc_id, educator=request.user)
        approved_drafts = doc.drafts.filter(is_approved=True, is_rejected=False)

        if approved_drafts.count() < 10:
            return Response({
                'success': False,
                'error': f'At least 10 approved questions are required to publish an assessment (Currently approved: {approved_drafts.count()}).'
            }, status=status.HTTP_400_BAD_REQUEST)

        school_ctx = None
        college_ctx = None
        subject_name = doc.title

        if academic_type == 'school' and academic_id:
            try:
                school_ctx = SchoolAcademicContext.objects.get(id=academic_id, educator=request.user)
                subject_name = school_ctx.subject
            except SchoolAcademicContext.DoesNotExist:
                pass
        elif academic_type == 'college' and academic_id:
            try:
                college_ctx = CollegeAcademicContext.objects.get(id=academic_id, educator=request.user)
                subject_name = college_ctx.subject
            except CollegeAcademicContext.DoesNotExist:
                pass

        # Create published Assessment
        assessment = Assessment.objects.create(
            educator=request.user,
            academic_type=academic_type or 'school',
            school_context=school_ctx,
            college_context=college_ctx,
            title=doc.title,
            subject=subject_name,
            is_published=True,
            published_at=timezone.now()
        )

        # Convert approved drafts into AssessmentQuestions
        created_questions = []
        for draft in approved_drafts:
            q = AssessmentQuestion.objects.create(
                assessment=assessment,
                question_text=draft.question_text,
                option_a=draft.option_a,
                option_b=draft.option_b,
                option_c=draft.option_c,
                option_d=draft.option_d,
                correct_answer=draft.correct_answer,
                explanation=draft.explanation,
                topic=draft.topic,
                source_reference=draft.source_reference,
                difficulty=draft.difficulty,
                discrimination_a=draft.provisional_discrimination,
                difficulty_b=draft.provisional_difficulty,
                is_calibrated=False
            )
            created_questions.append(q)

        return Response({
            'success': True,
            'assessment_id': assessment.id,
            'title': assessment.title,
            'questions_count': len(created_questions),
            'message': f'Assessment successfully published with {len(created_questions)} approved questions!'
        }, status=status.HTTP_201_CREATED)


class MatchAssessmentAPIView(APIView):
    """
    Exact matching endpoint: queries published assessments matching
    the educator-registered academic details.
    """
    permission_classes = [IsStudentUser]

    def post(self, request):
        academic_type = request.data.get('academic_type', '').strip().lower()

        NO_MATCH_MESSAGE = "No assessment is currently available for your selected academic details."

        if academic_type == 'school':
            school_name = request.data.get('school_name', '').strip()
            board = request.data.get('board', '').strip()
            standard = request.data.get('standard', '').strip()
            subject = request.data.get('subject', '').strip()

            if not all([school_name, board, standard, subject]):
                return Response({'found': False, 'message': 'All school academic fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

            matching_assessments = Assessment.objects.filter(
                is_published=True,
                academic_type='school',
                school_context__school_name__iexact=school_name,
                school_context__board__iexact=board,
                school_context__standard__iexact=standard,
                school_context__subject__iexact=subject
            )

        elif academic_type == 'college':
            college_name = request.data.get('college_name', '').strip()
            degree = request.data.get('degree', '').strip()
            academic_year = request.data.get('academic_year', '').strip()
            branch = request.data.get('branch', '').strip()
            subject = request.data.get('subject', '').strip()

            if not all([college_name, degree, academic_year, branch, subject]):
                return Response({'found': False, 'message': 'All college academic fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

            matching_assessments = Assessment.objects.filter(
                is_published=True,
                academic_type='college',
                college_context__college_name__iexact=college_name,
                college_context__degree__iexact=degree,
                college_context__academic_year__iexact=academic_year,
                college_context__branch__iexact=branch,
                college_context__subject__iexact=subject
            )

        else:
            return Response({'found': False, 'message': 'Invalid academic type specified.'}, status=status.HTTP_400_BAD_REQUEST)

        # Filter assessments that have at least 10 approved questions
        valid_assessment = None
        for a in matching_assessments:
            if a.questions.count() >= 10:
                valid_assessment = a
                break

        if not valid_assessment:
            return Response({
                'found': False,
                'message': NO_MATCH_MESSAGE
            }, status=status.HTTP_200_OK)

        return Response({
            'found': True,
            'assessment': {
                'id': valid_assessment.id,
                'title': valid_assessment.title,
                'subject': valid_assessment.subject,
                'academic_type': valid_assessment.academic_type,
                'question_count': valid_assessment.questions.count(),
                'target_length': 10
            }
        }, status=status.HTTP_200_OK)


@student_required
def assessment_instructions_view(request, assessment_id):
    """
    Goal 1: Pre-exam instructions, system readiness checklist, and anti-cheat agreement.
    """
    assessment = get_object_or_404(Assessment, id=assessment_id, is_published=True)

    # Check for active in-progress attempt
    active_attempt = AssessmentAttempt.objects.filter(
        student=request.user,
        assessment=assessment,
        status='in_progress'
    ).first()

    context = {
        'assessment': assessment,
        'active_attempt': active_attempt,
        'duration_minutes': 15,
        'target_questions': 10,
    }
    return render(request, 'assessment_instructions.html', context)


class StartAssessmentAPIView(APIView):
    """
    Goal 1: Initializes or resumes an AssessmentAttempt for the authenticated student.
    """
    permission_classes = [IsStudentUser]

    def post(self, request):
        assessment_id = request.data.get('assessment_id')
        if not assessment_id:
            return Response({'error': 'assessment_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        assessment = get_object_or_404(Assessment, id=assessment_id, is_published=True)

        # Check for existing in-progress attempt
        attempt = AssessmentAttempt.objects.filter(
            student=request.user,
            assessment=assessment,
            status='in_progress'
        ).first()

        if not attempt:
            attempt = AssessmentAttempt.objects.create(
                student=request.user,
                assessment=assessment,
                status='in_progress',
                adaptive_mode='IRT_ONLY'
            )

        return Response({
            'success': True,
            'attempt_id': attempt.id,
            'assessment_id': assessment.id,
            'redirect_url': f'/student/assessment/{attempt.id}/test/'
        }, status=status.HTTP_201_CREATED)


@student_required
def assessment_exam_view(request, attempt_id):
    """
    Goal 2: Dedicated Exam Room view presenting questions one-by-one
    with live countdown timer and active proctoring status.
    """
    attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, student=request.user)

    if attempt.status == 'completed':
        return redirect('student_assessment_completed', attempt_id=attempt.id)
    if attempt.status == 'terminated':
        return redirect('student_assessment_terminated', attempt_id=attempt.id)

    # Check 15-minute time limit
    duration_seconds = 15 * 60
    elapsed_seconds = (timezone.now() - attempt.started_at).total_seconds()
    remaining_seconds = max(0, int(duration_seconds - elapsed_seconds))

    if remaining_seconds <= 0:
        attempt.status = 'completed'
        attempt.completed_at = timezone.now()
        correct_count = attempt.responses.filter(is_correct=True).count()
        total_resp = attempt.responses.count()
        attempt.raw_score = correct_count
        attempt.accuracy = round((correct_count / max(1, total_resp)) * 100, 2)
        attempt.save(update_fields=['status', 'completed_at', 'raw_score', 'accuracy'])
        return redirect('student_assessment_completed', attempt_id=attempt.id)

    # Check integrity strikes
    warning_count = attempt.integrity_events.count()
    if warning_count >= 3:
        attempt.status = 'terminated'
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=['status', 'completed_at'])
        return redirect('student_assessment_terminated', attempt_id=attempt.id)

    # Check responses answered
    answered_ids = list(attempt.responses.values_list('question_id', flat=True))
    question_sequence = len(answered_ids) + 1

    if question_sequence > 10:
        attempt.status = 'completed'
        attempt.completed_at = timezone.now()
        correct_count = attempt.responses.filter(is_correct=True).count()
        attempt.raw_score = correct_count
        attempt.accuracy = round((correct_count / 10.0) * 100, 2)
        attempt.save(update_fields=['status', 'completed_at', 'raw_score', 'accuracy'])
        return redirect('student_assessment_completed', attempt_id=attempt.id)

    # Adaptive Item Selection (Module 7: IRT + XGBoost)
    adaptive_engine = AdaptiveEngine()
    estimator = AbilityEstimator()

    past_responses = list(attempt.responses.select_related('question').order_by('question_sequence'))
    history_records = [
        {
            'is_correct': r.is_correct,
            'difficulty': r.question.difficulty_b,
            'discrimination': r.question.discrimination_a
        }
        for r in past_responses
    ]
    ability_state = estimator.estimate_ability(history_records)
    current_theta = ability_state['theta']
    current_se = ability_state['standard_error']

    if question_sequence == 1:
        active_question = adaptive_engine.select_initial_question(attempt.assessment)
    else:
        active_question, telemetry = adaptive_engine.select_next_question(
            attempt=attempt,
            current_theta=current_theta,
            current_se=current_se
        )
        if telemetry and 'mode' in telemetry:
            attempt.adaptive_mode = telemetry['mode']
            attempt.model_version = telemetry.get('model_version', attempt.model_version)
            attempt.save(update_fields=['adaptive_mode', 'model_version'])

    if not active_question:
        attempt.status = 'completed'
        attempt.completed_at = timezone.now()
        correct_count = attempt.responses.filter(is_correct=True).count()
        total_resp = max(1, attempt.responses.count())
        attempt.raw_score = correct_count
        attempt.accuracy = round((correct_count / total_resp) * 100, 2)
        attempt.final_theta = current_theta
        attempt.final_se = current_se
        attempt.save(update_fields=['status', 'completed_at', 'raw_score', 'accuracy', 'final_theta', 'final_se'])
        return redirect('student_assessment_completed', attempt_id=attempt.id)

    context = {
        'attempt': attempt,
        'assessment': attempt.assessment,
        'active_question': active_question,
        'question_sequence': question_sequence,
        'target_questions': 10,
        'remaining_seconds': remaining_seconds,
        'warning_count': warning_count,
        'warning_limit': 3,
    }
    return render(request, 'assessment_exam.html', context)


class IntegrityWarningAPIView(APIView):
    """
    Goal 3: Logs integrity infractions (fullscreen exit, tab switch, clipboard).
    Automatically terminates test on 3rd infraction.
    """
    permission_classes = [IsStudentUser]

    def post(self, request):
        attempt_id = request.data.get('attempt_id')
        event_type = request.data.get('event_type', '').strip().lower()

        valid_events = ['fullscreen_exit', 'tab_switch', 'clipboard_attempt']
        if event_type not in valid_events:
            return Response({'error': f'Invalid event_type. Must be one of: {valid_events}'}, status=status.HTTP_400_BAD_REQUEST)

        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, student=request.user)

        if attempt.status != 'in_progress':
            return Response({
                'terminated': True,
                'status': attempt.status,
                'redirect_url': f'/student/assessment/{attempt.id}/{attempt.status}/'
            }, status=status.HTTP_200_OK)

        # Deduplication safeguard: Prevent duplicate strike if identical event is received within 1.5 seconds
        last_event = attempt.integrity_events.order_by('-id').first()
        if last_event and last_event.event_type == event_type and (timezone.now() - last_event.timestamp).total_seconds() < 1.5:
            current_warnings = attempt.integrity_events.count()
            return Response({
                'terminated': current_warnings >= 3,
                'warning_count': current_warnings,
                'remaining_warnings': max(0, 3 - current_warnings),
                'message': f'Warning {current_warnings} of 3 recorded.'
            }, status=status.HTTP_200_OK)

        current_warnings = attempt.integrity_events.count() + 1
        IntegrityEvent.objects.create(
            attempt=attempt,
            event_type=event_type,
            warning_number=current_warnings
        )

        if current_warnings >= 3:
            attempt.status = 'terminated'
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=['status', 'completed_at'])
            return Response({
                'terminated': True,
                'warning_count': current_warnings,
                'redirect_url': f'/student/assessment/{attempt.id}/terminated/',
                'message': 'Maximum integrity violations reached (3/3). Test session terminated.'
            }, status=status.HTTP_200_OK)

        return Response({
            'terminated': False,
            'warning_count': current_warnings,
            'remaining_warnings': 3 - current_warnings,
            'message': f'Warning {current_warnings} of 3 recorded.'
        }, status=status.HTTP_200_OK)


class SubmitResponseAPIView(APIView):
    """
    Goal 4: Records student response, calculates correctness, updates progress.
    """
    permission_classes = [IsStudentUser]

    def post(self, request):
        attempt_id = request.data.get('attempt_id')
        question_id = request.data.get('question_id')
        selected_option = request.data.get('selected_option', '').strip().upper()

        if not all([attempt_id, question_id, selected_option]):
            return Response({'error': 'attempt_id, question_id, and selected_option are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if selected_option not in ['A', 'B', 'C', 'D']:
            return Response({'error': 'selected_option must be A, B, C, or D.'}, status=status.HTTP_400_BAD_REQUEST)

        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, student=request.user)

        if attempt.status != 'in_progress':
            return Response({
                'error': f'Assessment is {attempt.status}.',
                'status': attempt.status,
                'redirect_url': f'/student/assessment/{attempt.id}/{attempt.status}/'
            }, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(AssessmentQuestion, id=question_id, assessment=attempt.assessment)

        responses_count = attempt.responses.count()
        next_seq = responses_count + 1

        is_correct = (selected_option == question.correct_answer.upper())

        # Psychometric ability update (Module 7 IRT 2PL MAP)
        estimator = AbilityEstimator()
        prior_responses = list(attempt.responses.select_related('question').order_by('question_sequence'))
        history_before = [
            {
                'is_correct': r.is_correct,
                'difficulty': r.question.difficulty_b,
                'discrimination': r.question.discrimination_a
            }
            for r in prior_responses
        ]
        state_before = estimator.estimate_ability(history_before)
        theta_before = state_before['theta']

        history_after = history_before + [{
            'is_correct': is_correct,
            'difficulty': question.difficulty_b,
            'discrimination': question.discrimination_a
        }]
        state_after = estimator.estimate_ability(history_after)
        theta_after = state_after['theta']
        se_after = state_after['standard_error']

        # Fisher Information calculated for this item at theta_before
        item_info = calculate_item_information(theta_before, question.discrimination_a, question.difficulty_b)

        # XGBoost predicted probability if service is available
        pred_service = get_prediction_service()
        xgb_prob = None
        if pred_service.is_available():
            from ml.feature_engineering import extract_candidate_features
            recent_bools = [r['is_correct'] for r in history_before]
            hist_qs = StudentResponse.objects.filter(attempt__student=request.user, question__topic=question.topic)
            tot_topic = hist_qs.count()
            hist_top_acc = (hist_qs.filter(is_correct=True).count() / tot_topic) if tot_topic > 0 else 0.5
            feat = extract_candidate_features(
                candidate_difficulty=question.difficulty_b,
                candidate_discrimination=question.discrimination_a,
                current_theta=theta_before,
                current_se=state_before['standard_error'],
                historical_topic_accuracy=hist_top_acc,
                recent_responses=recent_bools,
                total_answered=responses_count
            )
            xgb_prob = pred_service.predict_probability(feat)

        StudentResponse.objects.create(
            attempt=attempt,
            question=question,
            question_sequence=next_seq,
            selected_option=selected_option,
            is_correct=is_correct,
            theta_before=theta_before,
            theta_after=theta_after,
            se_after=se_after,
            irt_information=round(item_info, 4),
            xgboost_predicted_prob=xgb_prob
        )

        if next_seq >= 10:
            attempt.status = 'completed'
            attempt.completed_at = timezone.now()
            correct_count = attempt.responses.filter(is_correct=True).count()
            attempt.raw_score = correct_count
            attempt.accuracy = round((correct_count / 10.0) * 100, 2)
            attempt.final_theta = theta_after
            attempt.final_se = se_after
            attempt.save(update_fields=['status', 'completed_at', 'raw_score', 'accuracy', 'final_theta', 'final_se'])

            return Response({
                'success': True,
                'completed': True,
                'sequence_answered': next_seq,
                'is_correct': is_correct,
                'redirect_url': f'/student/assessment/{attempt.id}/completed/'
            }, status=status.HTTP_200_OK)

        return Response({
            'success': True,
            'completed': False,
            'sequence_answered': next_seq,
            'next_sequence': next_seq + 1,
            'is_correct': is_correct,
            'redirect_url': f'/student/assessment/{attempt.id}/test/'
        }, status=status.HTTP_200_OK)


def generate_enhanced_justification(question, resp, selected_text, correct_text, options_dict):
    """
    Generates an in-depth, detail-oriented pedagogical diagnostic for the student.
    Provides conceptual foundation, detailed rationale, distractor breakdown, and exam takeaway.
    """
    topic = question.topic or "Curriculum Concept"
    is_correct = resp.is_correct
    sel_opt = resp.selected_option
    corr_opt = question.correct_answer.upper()
    base_expl = question.explanation or "The correct option directly satisfies the curriculum definition and rule."

    # 1. Detailed Step-by-Step Rationale
    rationale = base_expl
    if len(rationale.split()) < 25:
        rationale += (
            f" Specifically, in the standard methodology for {topic}, "
            f"Option {corr_opt} ('{correct_text}') is the mathematically and procedurally verified answer. "
            f"It fulfills all required criteria outlined in the syllabus notes without introducing procedural contradictions."
        )

    # 2. Conceptual Foundation
    concept_context = (
        f"This question tests rigorous mastery of '{topic}'. "
        f"In this domain, questions categorized under {question.difficulty} difficulty require recognizing "
        f"exact definitions, the precise order of procedural operations, and distinguishing between prerequisite steps "
        f"and subsequent execution phases."
    )

    # 3. Deep Distractor & Error Analysis
    if not is_correct:
        distractor_why = (
            f"You selected Option {sel_opt} ('{selected_text}'). "
            f"A common student pitfall in {topic} is confusing adjacent operational stages or misapplying "
            f"the criteria of Option {sel_opt} to this step. "
            f"While Option {sel_opt} is a recognized concept within this subject, it does not represent the action "
            f"or definition specifically targeted by this question ('{question.question_text}'). Option {corr_opt} ('{correct_text}') is the "
            f"unambiguously correct standard."
        )
    else:
        distractor_why = (
            f"You correctly identified Option {corr_opt} ('{correct_text}') and avoided common distractors such as Option {('A' if corr_opt != 'A' else 'C')}. "
            f"This demonstrates solid conceptual grasp without conflating prerequisite definitions with downstream steps."
        )

    # 4. Other Distractors Analysis
    other_distractors = []
    for opt_key, opt_text in options_dict.items():
        if opt_key != corr_opt and opt_key != sel_opt:
            other_distractors.append(f"Option {opt_key} ('{opt_text}')")
    other_distractors_text = ", ".join(other_distractors) if other_distractors else "the remaining choices"

    distractor_summary = (
        f"Note that {other_distractors_text} represent alternative stages or incorrect parameters designed to "
        f"evaluate conceptual precision. They fail to meet the specific requirements of the problem statement."
    )

    # 5. Key Exam Tip
    exam_tip = (
        f"When answering questions on {topic}, always verify the exact chronological or logical order of steps. "
        f"Review {question.source_reference or 'the course materials'} to consolidate this sequence in your memory."
    )

    return {
        'rationale': rationale,
        'concept_context': concept_context,
        'distractor_why': distractor_why,
        'distractor_summary': distractor_summary,
        'exam_tip': exam_tip,
    }


@student_required
def assessment_completed_view(request, attempt_id):
    """
    Goal 8.2: Detailed Assessment Result, Question-by-Question Review with Justifications,
    Time Taken, Ability Trajectory, Topic Mastery, and ZPD Recommendations.
    """
    attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, student=request.user)
    if attempt.status == 'in_progress':
        return redirect('student_assessment_exam', attempt_id=attempt.id)

    responses = list(attempt.responses.select_related('question').order_by('question_sequence'))

    review_data = []
    for resp in responses:
        q = resp.question
        options = [
            {'key': 'A', 'text': q.option_a, 'is_selected': resp.selected_option == 'A', 'is_correct': q.correct_answer.upper() == 'A'},
            {'key': 'B', 'text': q.option_b, 'is_selected': resp.selected_option == 'B', 'is_correct': q.correct_answer.upper() == 'B'},
            {'key': 'C', 'text': q.option_c, 'is_selected': resp.selected_option == 'C', 'is_correct': q.correct_answer.upper() == 'C'},
            {'key': 'D', 'text': q.option_d, 'is_selected': resp.selected_option == 'D', 'is_correct': q.correct_answer.upper() == 'D'},
        ]
        options_dict = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
        correct_option_text = getattr(q, f"option_{q.correct_answer.lower()}", "")
        selected_option_text = getattr(q, f"option_{resp.selected_option.lower()}", "")
        justification_pkg = generate_enhanced_justification(q, resp, selected_option_text, correct_option_text, options_dict)

        review_data.append({
            'sequence': resp.question_sequence,
            'question_text': q.question_text,
            'topic': q.topic,
            'difficulty': q.difficulty,
            'difficulty_b': q.difficulty_b,
            'discrimination_a': q.discrimination_a,
            'selected_option': resp.selected_option,
            'selected_text': selected_option_text,
            'correct_answer': q.correct_answer.upper(),
            'correct_text': correct_option_text,
            'is_correct': resp.is_correct,
            'explanation': q.explanation,
            'justification': justification_pkg,
            'source_reference': q.source_reference,
            'theta_before': resp.theta_before,
            'theta_after': resp.theta_after,
            'se_after': resp.se_after,
            'irt_information': resp.irt_information,
            'options': options,
        })

    # Trajectory data for Chart.js
    trajectory_labels = [f"Q{r['sequence']}" for r in review_data]
    trajectory_thetas = [round(r['theta_after'], 2) for r in review_data]
    trajectory_se_upper = [round(r['theta_after'] + r['se_after'], 2) for r in review_data]
    trajectory_se_lower = [round(r['theta_after'] - r['se_after'], 2) for r in review_data]
    trajectory_info = [round(r['irt_information'], 2) for r in review_data]

    # Topic Mastery Aggregation
    topic_stats = {}
    for r in review_data:
        t = r['topic']
        if t not in topic_stats:
            topic_stats[t] = {'total': 0, 'correct': 0}
        topic_stats[t]['total'] += 1
        if r['is_correct']:
            topic_stats[t]['correct'] += 1

    topic_mastery = []
    for topic, stats in topic_stats.items():
        acc = round((stats['correct'] / stats['total']) * 100, 1)
        if acc >= 75:
            tier = 'Mastered'
            tier_class = 'mastered'
        elif acc >= 50:
            tier = 'Developing'
            tier_class = 'developing'
        else:
            tier = 'Needs Review'
            tier_class = 'needs-review'

        topic_mastery.append({
            'topic': topic,
            'total': stats['total'],
            'correct': stats['correct'],
            'accuracy': acc,
            'tier': tier,
            'tier_class': tier_class,
        })
    topic_mastery.sort(key=lambda x: x['accuracy'])

    # ZPD Learning Recommendations
    final_theta = attempt.final_theta or 0.0
    zpd_min = round(final_theta - 0.5, 2)
    zpd_max = round(final_theta + 0.5, 2)

    needs_focus_topics = [t['topic'] for t in topic_mastery if t['tier'] in ['Needs Review', 'Developing']]
    mastered_topics = [t['topic'] for t in topic_mastery if t['tier'] == 'Mastered']

    recommendations = []
    if needs_focus_topics:
        recommendations.append({
            'type': 'priority',
            'title': 'High-Priority Concepts for Revision',
            'detail': f"Focus revision on: {', '.join(needs_focus_topics)}. Targeted practice here will yield the largest ability gains."
        })
    if mastered_topics:
        recommendations.append({
            'type': 'strength',
            'title': 'Consolidated Strengths',
            'detail': f"Strong conceptual mastery demonstrated in: {', '.join(mastered_topics)}. Maintain retention through periodic mixed recall."
        })

    recommendations.append({
        'type': 'zpd',
        'title': 'Zone of Proximal Development (ZPD) Challenge Band',
        'detail': f"Your calibrated ability is θ = {final_theta:+.2f}. For optimal cognitive challenge, practice questions with item difficulty b between {zpd_min:+.2f} and {zpd_max:+.2f}."
    })

    pace_per_question = None
    if attempt.duration_seconds and len(responses) > 0:
        pace_per_question = f"{round(attempt.duration_seconds / len(responses), 1)}s"

    if final_theta >= 1.2:
        theta_tier = "Advanced Mastery"
        theta_tier_color = "#10b981"
    elif final_theta >= 0.3:
        theta_tier = "Proficient"
        theta_tier_color = "#6366f1"
    elif final_theta >= -0.5:
        theta_tier = "Intermediate"
        theta_tier_color = "#f59e0b"
    else:
        theta_tier = "Foundational"
        theta_tier_color = "#ef4444"

    confidence_index = round(max(50.0, min(99.0, 100.0 - ((attempt.final_se or 0.3) * 50.0))), 1)

    context = {
        'attempt': attempt,
        'review_data': review_data,
        'trajectory_labels': json.dumps(trajectory_labels),
        'trajectory_thetas': json.dumps(trajectory_thetas),
        'trajectory_se_upper': json.dumps(trajectory_se_upper),
        'trajectory_se_lower': json.dumps(trajectory_se_lower),
        'trajectory_info': json.dumps(trajectory_info),
        'topic_mastery': topic_mastery,
        'recommendations': recommendations,
        'zpd_min': zpd_min,
        'zpd_max': zpd_max,
        'pace_per_question': pace_per_question,
        'theta_tier': theta_tier,
        'theta_tier_color': theta_tier_color,
        'confidence_index': confidence_index,
    }
    return render(request, 'assessment_completed.html', context)


@student_required
def assessment_terminated_view(request, attempt_id):
    """
    Goal 5: Security Lockout / Termination screen displaying violation history.
    """
    attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, student=request.user)
    events = attempt.integrity_events.all().order_by('timestamp')
    return render(request, 'assessment_terminated.html', {'attempt': attempt, 'events': events})


