"""
Biostar views
"""
from main.server import html, models
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.http import HttpResponse

# the openid association model
from django_openid_auth.models import UserOpenID

def index(request):
    "Main page"
    
    
    # attempts to migrate the user
    if request.user.is_authenticated():
        users = detect_duplicates(request)
        if users:
            return merge_accounts(request, users)
    
    '''    
    if settings.DEBUG:
        if request.user.is_authenticated() and not request.user.profile.is_admin:
            request.user.profile.type = models.USER_ADMIN
            request.user.profile.save()
    '''
    
    # shows both the 5 freshest and 5 oldest questions 
    # (this is for debugging)
    
    qs = models.Question.objects.select_related('post', 'post__author','post__author__profile').all()
    
    top = qs.order_by('-lastedit_date')[:5]
    bot = qs.order_by('lastedit_date')[:5]
    questions = list(top) + list(bot)
    return html.template( request, name='index.html', questions=questions)

def admin_password_override(request):
    """
    This view is active only if the ALLOW_ADMIN_OVERRIDE setting is True.
    Allows anyone to log in and personify any other user as long as they enter
    the content of SECRET_KEY as password. This needs to be True during testing.
    """
    if request.method=='GET':
        return html.template( request, name='admin.password.override.html')
    else:
        uid = request.POST.get('uid', '')
        passwd = request.POST.get('password', '')
        if passwd == settings.SECRET_KEY:
            user = models.User.objects.get(pk=uid)
            if 'set_type' in request.POST: # Allow setting of user type for testing
                user.profile.type = int(request.POST.get('set_type'))
                user.profile.save()
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return html.redirect('/') 
        
    raise Exception('Invalid login')

def detect_duplicates(request):
    "Detects duplicate users"
    users = models.User.objects.filter(email=request.user.email).order_by('date_joined')
    users = list(users)
    if len(users)==2:
        return users[0], users[1]
    else:
        return None
    
@transaction.commit_on_success
def merge_accounts(request, users):
    "Attempts to merge user accounts if emails match"
    
    openid = UserOpenID.objects.get(user=request.user)
    openid.user = users[0]
    openid.save()
    
    # log out the current user
    logout(request)
    
    # delete the user just created via OpenID
    target = models.User.objects.get(id=users[1].id)
    target.delete()
    
    return html.template(request, name='account.merge.html')
        
def user_profile(request, uid):
    "User's profile page"
    user = models.User.objects.get(id=uid)
    profile = models.UserProfile.objects.get(user=user)
    questions = models.Question.objects.filter(post__author=user).select_related('post','post__author','post__author__profile')
    answers = models.Answer.objects.filter(post__author=user).select_related('post','question','question__post','question__post__author','question__post__author__profile')

    return html.template(request, name='user.profile.html',
      user=user, profile=profile,
      questions=questions.order_by('-post__score'),
      answers=answers.order_by('-post__score'))

def get_page(request, obj_list, per_page=25):
    "A generic paginator"

    paginator = Paginator(obj_list, per_page) 
    try:
        pid = int(request.GET.get('page', '1'))
    except ValueError:
        pid = 1

    try:
        page = paginator.page(pid)
    except (EmptyPage, InvalidPage):
        page = paginator.page(paginator.num_pages)
    
    return page

def user_list(request):
    users = models.User.objects.all()
    page  = get_page(request, users)
    return html.template(request, name='user.list.html', page=page)

def tag_list(request):
    tags = models.Tag.objects.all().order_by('-count')
    page = get_page(request, tags, per_page=50)
    return html.template(request, name='tag.list.html', page=page)

def badge_list(request):
    badges = models.Badge.objects.filter(secret=False).order_by('name')
    return html.template(request, name='badge.list.html', badges=badges)

def search(request):
    return html.template(request, name='todo.html')

def questions():
    " Returns a common queryset that can be used to select questions"
    return models.Question.objects.select_related('post', 'post__author','post__author__profile')

def question_list(request):
    "Lists all the questions"
    qs = questions().all()
    page = get_page(request, qs) 
    return html.template(request, name='question.list.html', page=page)

def question_tagged(request, tag_name):
    qs = questions().filter(post__tag_set__name=tag_name)
    page = get_page(request, qs) 
    return html.template(request, name='question.list.html', page=page)

def question_unanswered(request):
    qs = questions().filter(answer_count=0)
    page = get_page(request, qs) 
    return html.template(request, name='question.list.html', page=page)
    

def question_show(request, pid):
    "Returns a question with all answers"
    qs = models.Question.all_objects if 'view_deleted' in request.permissions else models.Question.objects
    question = qs.get(id=pid)
    if request.user.is_authenticated():
        question.post.views += 1
        question.post.save()
    qs = models.Answer.all_objects if 'view_deleted' in request.permissions else models.Answer.objects
    answers  = qs.filter(question=question).select_related('post','post__author','post__author__profile')
    answers = answers.order_by('-accepted','-post__score')
    return html.template( request, name='question.show.html', question=question, answers=answers )

# question form and its default values
_Q_TITLE, _Q_CONTENT, _Q_TAG = 'Question title', 'question content', 'tag1'
class QuestionForm(forms.Form):
    "A form representing a new question"
    title   = forms.CharField(max_length=250,  initial=_Q_TITLE)
    content = forms.CharField(max_length=5000, initial=_Q_CONTENT)
    tags    = forms.CharField(max_length=250,  initial=_Q_TAG)
    
    def clean(self):
        "Custom validator for the question"
        if self.cleaned_data['tags'] == _Q_TAG:
            raise forms.ValidationError("Please change the tag from default value")
    
        if self.cleaned_data['content'] == _Q_CONTENT:
            raise forms.ValidationError("Please change content from default value")
        
        if self.cleaned_data['title'] == _Q_TITLE:
            raise forms.ValidationError("Please change title from default value")

        return self.cleaned_data

# editing questions/answers and comments can be merged into a single post handler
# for now these are separete to allow us to identify what each step needs

@login_required(redirect_field_name='/openid/login/')
def question_edit(request, pid=0):
    "Handles questions"
    
    # pid == 0 means a new question
    asknew = pid == 0
    edit = not asknew

    # rather than nesting ifs lets deal with each case separately 
    # then exit as soon as we got enough information
    if asknew:
        params = html.Params(subheader='Ask a question', button='Ask your question')
    else:
        params = html.Params(subheader='Edit question', button='Submit changes')

    # looks like a new question
    if asknew and request.method == 'GET':
        form = QuestionForm()
        return html.template( request, name='edit.question.html', form=form, params=params)
    
    # looks like starting an edit request for an existing question
    if edit and request.method == 'GET':
        question = models.Question.objects.get(pk=pid)
        question.authorize(request)
        tags = question.post.tag_string
        form = QuestionForm(initial=dict(title=question.post.title, content=question.post.content, tags=tags))
        return html.template( request, name='edit.question.html', form=form, params=params)
  
    # we can only deal with POST after this point
    assert  request.method == 'POST'
    
    # check the form for validity
    form = QuestionForm(request.POST)
    if not form.is_valid():
        return html.template( request, name='edit.question.html', form=form, params=params)

    # at this point the form is valid
    title   = form.cleaned_data['title']
    content = form.cleaned_data['content']
    tags    = form.cleaned_data['tags'].split()
            
    if asknew:
        # generate the new question
        post = models.Post.objects.create(author=request.user)
        post.create_revision(content=content, tag_string=' '.join(tags), title=title)
        question = models.Question.objects.create(post=post)
    else:
        # editing existing question
        question = models.Question.objects.get(pk=pid)
        post = question.post
        post.create_revision(content=content, title=title, tag_string=' '.join(tags), author=request.user)

    # show the question
    return html.redirect('/question/show/%s/' % question.id) 
            

# answer/comment form and its default values
class AnswerForm(forms.Form):
    "A form representing an answer or comment"
    content = forms.CharField(max_length=5000)

@login_required(redirect_field_name='/openid/login/')
def answer_edit(request, qid, aid=0):
    "Handles answers, question id and answer id"
    
    # get the question that is to be accessed
    question = models.Question.objects.get(pk=qid)

    newans = aid == 0
    edit = not newans

    if edit and request.method == 'GET':
        # editing an existing answer
        answer = models.Answer.objects.get(pk=aid)
        answer.authorize(request)
        form = AnswerForm( initial=dict(content=answer.post.content) )
        return html.template( request, name='edit.answer.html', form=form)

    # only POST remains at this point
    assert request.method == 'POST'
    
    # incoming  data
    form = AnswerForm(request.POST)
    if not form.is_valid():
        # invalid form render the errors
        return html.template( request, name='edit.answer.html', form=form)

    # at this point the data is valid
    content = form.cleaned_data['content']

    if newans:
        # new answer for the question
        post = models.Post.objects.create(author=request.user)
        post.create_revision(content=content)
        answer = models.Answer.objects.create(post=post, question=question)
    else:
        # update the answer
        answer = models.Answer.objects.get(pk=aid)
        answer.authorize(request)
        answer.post.create_revision(content=content, author=request.user)

    return html.redirect('/question/show/%s/' % qid)
    
def revision_list(request, pid):
    post = models.Post.objects.get(pk=pid)
    revisions = list(post.revisions.order_by('date')) # Oldest first, will need to be reversed later
    
    # We need to annotate the revisions with exactly what was changed
    # 'verb' is a word for the action box to describe the revision
    # 'modified' is a list (title, content, tag_string) of boolean values for if it was changed
    def revision_data(rev):
        return rev.title, rev.content, rev.tag_string
    last_data = revision_data(revisions[0])
    revisions[0].verb = 'created'
    revisions[0].modified = [True, True, True] # Always display the first revision
    for revision in revisions[1:]:
        if revision.action:
            revision.verb = 'performed'
        else:
            revision.verb = 'edited'
            data = revision_data(revision)
            revision.modified = [current != last for current, last in zip(data, last_data)]
            last_data = data
    revisions.reverse()
    
    return html.template(request, name='revision.list.html', revisions=revisions, post=post)
   
@login_required(redirect_field_name='/openid/login/')
def comment_add(request, pid):
    
    parent = models.Post.objects.get(pk=pid)
    content = request.POST['text']
    post = models.Post(author=request.user)
    post.html = post.content = html.sanitize(content, allowed_tags='')
    post.save()
    comment = models.Comment(parent=parent, post=post)
    comment.save()

    try:
        return html.redirect('/question/show/%s/' % (parent.question.id))
    except models.Question.DoesNotExist:
        return html.redirect('/question/show/%s/#%s' % (parent.answer.question.id, parent.answer.id))

def vote(request):
    "Handles all voting on posts"
    if request.method == 'POST':
        
        author = request.user
        if not author.is_authenticated():
            return html.json_response({'status':'error', 'msg':'You must be logged in to vote'})
        
        post_id = int(request.POST.get('post'))
        post = models.Post.objects.get(id=post_id)
        
        if post.author == author:
            return html.json_response({'status':'error', 'msg':'You cannot vote on your own post'})
        
        type = int(request.POST.get('type'))
        
        old_vote = post.get_vote(author, type)
        if old_vote:
            old_vote.delete()
            return html.json_response({
                'status':'success',
                'msg':'%s removed' % old_vote.get_type_display()})
        else:
            vote = post.add_vote(author, type)
            if type in models.OPPOSING_VOTES: 
                # Remove an opposing vote if it exists
                post.remove_vote(author, models.OPPOSING_VOTES[type])
            return html.json_response({
                'status':'success',
                'msg':'%s added' % vote.get_type_display()})
                    

    return html.json_response({'status':'error', 'msg':'POST method must be used'})

def moderate(request):
    if request.method == 'POST':
        author = request.user
        if 'moderate_post' not in request.permissions: # Need to also check for actual mod permissions
            return html.json_response({'status':'error', 'msg':'You do not have permission to moderate posts.'})        

        post_id = int(request.POST.get('post'))
        post = models.Post.objects.get(id=post_id)
        
        action = request.POST.get('action')
        action_map = {'close':models.REV_CLOSE, 'reopen':models.REV_REOPEN,
                      'delete':models.REV_DELETE, 'undelete':models.REV_UNDELETE}
        post.moderator_action(action_map[action], author)
        
        return html.json_response({'status':'success', 'msg':'%s performed' % action})
        
    return html.json_response({'status':'error', 'msg':'POST method must be used'})
        


@login_required(redirect_field_name='/openid/login/')
def preview(request):
    "This runs the markdown preview functionality"
    content = request.POST.get('content','no input')

    try:
        output = html.generate(content)
    except KeyError, exc:
        # return more userfriendly errors, used for debugging
        output = 'Error: %s' % str(exc)

    return HttpResponse(output, mimetype='text/plain')