from django.shortcuts import render

# Create your views here.
def index(request, *args, **kwargs):
   return render(request, 'index.html')

def test(request, *args, **kwargs):
   return render(request, 'test_app/text.html')

def test2(request, *args, **kwargs):
   return render(request, 'test.html')

def media_image(request, filename):
    """
    Serve media images from the 'media' directory.
    """
    return render(request, 'media/' + filename)