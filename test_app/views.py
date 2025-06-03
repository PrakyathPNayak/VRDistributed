from django.shortcuts import render

# Create your views here.
def index(request, *args, **kwargs):
   return render(request, 'index.html')

def test(request, *args, **kwargs):
   return render(request, 'test_app/text.html')

def test2(request, *args, **kwargs):
   return render(request, 'test.html')