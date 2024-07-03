from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def hello_rest_api(request):
    data = {'message': '하이 기환~!'}
    return Response(data)