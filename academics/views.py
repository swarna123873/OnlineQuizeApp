from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import SchoolAcademicContext, CollegeAcademicContext

class SchoolDropdownOptionsAPIView(APIView):
    """
    Dynamically returns cascading dropdown options strictly populated
    from educator-registered academic records in the database.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        field = request.query_params.get('field', 'school_name')
        school_name = request.query_params.get('school_name', '').strip()
        board = request.query_params.get('board', '').strip()
        state = request.query_params.get('state', '').strip()
        standard = request.query_params.get('standard', '').strip()

        qs = SchoolAcademicContext.objects.all()

        if field == 'school_name':
            schools = qs.values_list('school_name', flat=True).distinct().order_by('school_name')
            return Response({'field': 'school_name', 'options': list(schools)})

        if school_name:
            qs = qs.filter(school_name__iexact=school_name)

        if field == 'board':
            boards = qs.values_list('board', flat=True).distinct().order_by('board')
            return Response({'field': 'board', 'options': list(boards)})

        if board:
            qs = qs.filter(board__iexact=board)

        if field == 'state':
            states = qs.exclude(state='').values_list('state', flat=True).distinct().order_by('state')
            return Response({'field': 'state', 'options': list(states)})

        if state:
            qs = qs.filter(state__iexact=state)

        if field == 'standard':
            standards = qs.values_list('standard', flat=True).distinct().order_by('standard')
            return Response({'field': 'standard', 'options': list(standards)})

        if standard:
            qs = qs.filter(standard__iexact=standard)

        if field == 'subject':
            subjects = qs.values_list('subject', flat=True).distinct().order_by('subject')
            return Response({'field': 'subject', 'options': list(subjects)})

        return Response({'error': 'Invalid field requested.'}, status=status.HTTP_400_BAD_REQUEST)


class CollegeDropdownOptionsAPIView(APIView):
    """
    Dynamically returns cascading dropdown options strictly populated
    from educator-registered college academic records in the database.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        field = request.query_params.get('field', 'college_name')
        college_name = request.query_params.get('college_name', '').strip()
        degree = request.query_params.get('degree', '').strip()
        academic_year = request.query_params.get('academic_year', '').strip()
        branch = request.query_params.get('branch', '').strip()
        classification = request.query_params.get('classification', '').strip()

        qs = CollegeAcademicContext.objects.all()

        if field == 'college_name':
            colleges = qs.values_list('college_name', flat=True).distinct().order_by('college_name')
            return Response({'field': 'college_name', 'options': list(colleges)})

        if college_name:
            qs = qs.filter(college_name__iexact=college_name)

        if field == 'degree':
            degrees = qs.values_list('degree', flat=True).distinct().order_by('degree')
            return Response({'field': 'degree', 'options': list(degrees)})

        if degree:
            qs = qs.filter(degree__iexact=degree)

        if field == 'academic_year':
            years = qs.values_list('academic_year', flat=True).distinct().order_by('academic_year')
            return Response({'field': 'academic_year', 'options': list(years)})

        if academic_year:
            qs = qs.filter(academic_year__iexact=academic_year)

        if field == 'branch':
            branches = qs.values_list('branch', flat=True).distinct().order_by('branch')
            return Response({'field': 'branch', 'options': list(branches)})

        if branch:
            qs = qs.filter(branch__iexact=branch)

        if field == 'classification':
            classifications = qs.values_list('classification', flat=True).distinct().order_by('classification')
            return Response({'field': 'classification', 'options': list(classifications)})

        if classification:
            qs = qs.filter(classification__iexact=classification)

        if field == 'subject':
            subjects = qs.values_list('subject', flat=True).distinct().order_by('subject')
            return Response({'field': 'subject', 'options': list(subjects)})

        return Response({'error': 'Invalid field requested.'}, status=status.HTTP_400_BAD_REQUEST)
