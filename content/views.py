import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from accounts.permissions import educator_required, IsEducatorUser
from academics.models import SchoolAcademicContext, CollegeAcademicContext
from .models import UploadedDocument, QuestionDraft
from .serializers import QuestionDraftSerializer, UploadedDocumentSerializer
from .pdf_extractor import PDFExtractor, PDFExtractionError
from .llm_service import get_llm_provider, GroqLLMProvider

@educator_required
def educator_dashboard_view(request):
    """
    Landing page for Educators/Schools with two clear paths:
    1. School Educator workflow
    2. College Educator workflow
    """
    total_docs = UploadedDocument.objects.filter(educator=request.user).count()
    total_drafts = QuestionDraft.objects.filter(educator=request.user).count()
    approved_drafts = QuestionDraft.objects.filter(educator=request.user, is_approved=True).count()
    groq_configured = GroqLLMProvider().is_configured()

    context = {
        'total_docs': total_docs,
        'total_drafts': total_drafts,
        'approved_drafts': approved_drafts,
        'groq_configured': groq_configured,
    }
    return render(request, 'educator_dashboard.html', context)

@educator_required
def school_form_view(request):
    return render(request, 'school_form.html')

@educator_required
def college_form_view(request):
    return render(request, 'college_form.html')

@educator_required
def educator_review_view(request, doc_id):
    document = get_object_or_404(UploadedDocument, id=doc_id, educator=request.user)
    drafts = document.drafts.all().order_by('id')
    approved_count = drafts.filter(is_approved=True).count()
    return render(request, 'review_questions.html', {
        'document': document,
        'drafts': drafts,
        'approved_count': approved_count,
    })


class UploadAndGenerateAPIView(APIView):
    """
    API to upload one or more PDFs, extract text from all of them with PyMuPDF,
    register the academic context, and generate draft MCQs using the LLM provider
    from the combined content of all uploaded files.

    Accepts: pdf_files[] (multiple) or pdf_file (single, for backward compatibility)
    """
    permission_classes = [IsEducatorUser]

    def post(self, request):
        # Accept multiple files: pdf_files, pdf_files[], or pdf_file
        pdf_files = (
            request.FILES.getlist('pdf_files') or
            request.FILES.getlist('pdf_files[]') or
            request.FILES.getlist('pdf_file')
        )
        if not pdf_files and request.FILES:
            pdf_files = list(request.FILES.values())

        if not pdf_files:
            return Response(
                {'error': 'Please upload at least one PDF file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate ALL files before processing any
        for f in pdf_files:
            try:
                PDFExtractor.validate_file(f)
            except PDFExtractionError as e:
                return Response(
                    {'error': f'File "{f.name}": {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        academic_type = request.data.get('academic_type', '').strip().lower()
        title = request.data.get('assessment_title', '').strip() or pdf_files[0].name

        # --- Academic context registration ---
        academic_context_id = None
        subject_name = ""

        if academic_type == 'school':
            school_name = request.data.get('school_name', '').strip()
            board = request.data.get('board', '').strip()
            state = request.data.get('state', '').strip()
            standard = request.data.get('standard', '').strip()
            subject_name = request.data.get('subject', '').strip()

            if not all([school_name, board, standard, subject_name]):
                return Response(
                    {'error': 'School name, board, standard, and subject are required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            school_ctx, _ = SchoolAcademicContext.objects.get_or_create(
                educator=request.user,
                school_name=school_name,
                board=board,
                state=state,
                standard=standard,
                subject=subject_name
            )
            academic_context_id = school_ctx.id

        elif academic_type == 'college':
            college_name = request.data.get('college_name', '').strip()
            degree = request.data.get('degree', '').strip()
            academic_year = request.data.get('academic_year', '').strip()
            branch = request.data.get('branch', '').strip()
            classification = request.data.get('classification', '').strip()
            subject_name = request.data.get('subject', '').strip()

            if not all([college_name, degree, academic_year, branch, classification, subject_name]):
                return Response(
                    {'error': 'College name, degree, academic year, branch, classification, and subject are required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            college_ctx, _ = CollegeAcademicContext.objects.get_or_create(
                educator=request.user,
                college_name=college_name,
                degree=degree,
                academic_year=academic_year,
                branch=branch,
                classification=classification,
                subject=subject_name
            )
            academic_context_id = college_ctx.id

        else:
            return Response(
                {'error': "Invalid academic_type. Must be 'school' or 'college'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Multi-PDF: save each file, extract, combine all chunks ---
        saved_docs = []
        all_combined_chunks = []
        primary_doc = None

        for idx, pdf_file in enumerate(pdf_files):
            if idx == 0:
                file_title = title
            else:
                file_title = f"{title} (Part {idx + 1}: {pdf_file.name})"

            doc = UploadedDocument.objects.create(
                educator=request.user,
                title=file_title,
                file=pdf_file
            )

            try:
                extraction = PDFExtractor.extract_text_and_chunks(doc.file.path)
                doc.extracted_text = extraction['full_text']
                doc.total_pages = extraction['total_pages']
                doc.is_ocr_required = extraction['is_ocr_required']
                doc.save()

                if doc.is_ocr_required:
                    saved_docs.append({
                        'doc': doc,
                        'skipped': True,
                        'reason': f'"{pdf_file.name}" requires OCR and was skipped.'
                    })
                    continue

                # Tag every chunk with its source filename for LLM context
                for chunk in extraction['chunks']:
                    chunk['source'] = f"{pdf_file.name} — {chunk.get('source', 'Page')}"
                all_combined_chunks.extend(extraction['chunks'])
                saved_docs.append({'doc': doc, 'skipped': False})

                if primary_doc is None:
                    primary_doc = doc

            except Exception as e:
                return Response(
                    {'error': f'Text extraction failed for "{pdf_file.name}": {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        if not all_combined_chunks or primary_doc is None:
            return Response({
                'success': False,
                'error': 'No extractable text found in any uploaded PDF. Files may be scanned images requiring OCR.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update primary doc total pages across all processed PDFs
        total_valid_pages = sum(d['doc'].total_pages for d in saved_docs if not d.get('skipped'))
        primary_doc.total_pages = total_valid_pages
        primary_doc.save(update_fields=['total_pages'])


        # Uniformly generate exactly 50 questions across single or multiple PDFs
        num_questions = 50

        # --- Generate MCQs from ALL combined chunks via Groq ---
        llm = get_llm_provider()
        try:
            raw_questions = llm.generate_mcqs(
                all_combined_chunks,
                subject=subject_name,
                num_questions=num_questions
            )
        except Exception as e:
            return Response(
                {'error': f"Question generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        created_drafts = []
        for q_data in raw_questions:
            draft = QuestionDraft(
                document=primary_doc,  # linked to first/primary doc for review routing
                educator=request.user,
                question_text=q_data.get('question_text', '').strip(),
                option_a=q_data.get('option_a', '').strip(),
                option_b=q_data.get('option_b', '').strip(),
                option_c=q_data.get('option_c', '').strip(),
                option_d=q_data.get('option_d', '').strip(),
                correct_answer=q_data.get('correct_answer', 'A').strip().upper()[:1],
                explanation=q_data.get('explanation', '').strip(),
                topic=q_data.get('topic', subject_name).strip(),
                source_reference=q_data.get('source_reference', '').strip(),
                difficulty=q_data.get('difficulty', 'Medium').strip().capitalize(),
            )
            draft.assign_provisional_irt_parameters()
            draft.save()
            created_drafts.append(draft)

        skipped_files = [s['reason'] for s in saved_docs if s.get('skipped')]
        extracted_count = len([s for s in saved_docs if not s.get('skipped')])

        return Response({
            'success': True,
            'document_id': primary_doc.id,
            'documents_uploaded': len(pdf_files),
            'pdfs_extracted': extracted_count,
            'academic_context_id': academic_context_id,
            'academic_type': academic_type,
            'drafts_count': len(created_drafts),
            'drafts': QuestionDraftSerializer(created_drafts, many=True).data,
            'skipped_files': skipped_files,
            'message': (
                f"Extracted {len(all_combined_chunks)} text chunks from {extracted_count} of {len(pdf_files)} PDF(s). "
                f"Generated {len(created_drafts)} draft MCQs from the combined content."
            )
        }, status=status.HTTP_201_CREATED)


class QuestionDraftDetailAPIView(APIView):
    """
    Educator review API: view, update, correct answer, approve, or reject.
    """
    permission_classes = [IsEducatorUser]

    def get(self, request, pk):
        draft = get_object_or_404(QuestionDraft, pk=pk, educator=request.user)
        return Response(QuestionDraftSerializer(draft).data)

    def patch(self, request, pk):
        draft = get_object_or_404(QuestionDraft, pk=pk, educator=request.user)
        serializer = QuestionDraftSerializer(draft, data=request.data, partial=True)
        if serializer.is_valid():
            draft = serializer.save()
            if 'difficulty' in request.data:
                draft.assign_provisional_irt_parameters()
                draft.save()
            return Response(QuestionDraftSerializer(draft).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        draft = get_object_or_404(QuestionDraft, pk=pk, educator=request.user)
        draft.delete()
        return Response({'success': True, 'message': 'Draft deleted.'})


class BulkApproveDraftsAPIView(APIView):
    """
    Allows educator to approve eligible drafts for an assessment.
    """
    permission_classes = [IsEducatorUser]

    def post(self, request):
        draft_ids = request.data.get('draft_ids', [])
        if draft_ids:
            updated = QuestionDraft.objects.filter(
                id__in=draft_ids,
                educator=request.user
            ).update(is_approved=True, is_rejected=False)
        else:
            doc_id = request.data.get('document_id')
            if doc_id:
                updated = QuestionDraft.objects.filter(
                    document_id=doc_id,
                    educator=request.user
                ).update(is_approved=True, is_rejected=False)
            else:
                updated = 0

        return Response({
            'success': True,
            'approved_count': updated,
            'message': f"Approved {updated} question(s)."
        })
