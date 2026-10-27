from rest_framework import serializers
from .models import UploadedDocument, QuestionDraft

class QuestionDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionDraft
        fields = [
            'id', 'document', 'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'topic', 'source_reference',
            'difficulty', 'provisional_difficulty', 'provisional_discrimination',
            'is_approved', 'is_rejected', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'provisional_difficulty', 'provisional_discrimination']

class UploadedDocumentSerializer(serializers.ModelSerializer):
    draft_count = serializers.IntegerField(source='drafts.count', read_only=True)

    class Meta:
        model = UploadedDocument
        fields = ['id', 'title', 'total_pages', 'is_ocr_required', 'uploaded_at', 'draft_count']
