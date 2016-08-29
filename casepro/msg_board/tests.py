from casepro.test import BaseCasesTest
from django.core.urlresolvers import reverse
from django.test import Client
from django_comments.models import Comment
from django_comments.forms import CommentForm
from casepro.msg_board.models import PinnedComment


class CommentTest(BaseCasesTest):
    def setUp(self):
        super(CommentTest, self).setUp()
        self.client = Client()
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann",
                                       fields={'age': "34"},
                                       groups=[self.females, self.reporters, self.registered])
        self.login(self.user1)

    def test_post_comment(self):
        data = CommentForm(self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo',
        })
        response = self.url_post(
            'unicef',
            reverse('comments-post-comment'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.all().count(), 1)
        self.assertEqual(Comment.objects.all().first().comment, 'Foo')

    def test_pin_comment(self):
        self.assertEqual(PinnedComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.unicef,
            reverse('comments-post-comment'), data)
        self.assertEqual(Comment.objects.all().count(), 1)
        response = self.url_post(
            self.unicef,
            reverse('msg_board.pinnedcomment_pin', kwargs={'pk': Comment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PinnedComment.objects.all().count(), 1)

    def test_unpin_comment(self):
        self.assertEqual(PinnedComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.unicef,
            reverse('comments-post-comment'), data)
        self.assertEqual(Comment.objects.all().count(), 1)
        response = self.url_post(
            self.unicef,
            reverse('msg_board.pinnedcomment_pin', kwargs={'pk': Comment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PinnedComment.objects.all().count(), 1)
        response = self.url_post(
            self.unicef,
            reverse('msg_board.pinnedcomment_unpin', kwargs={'pk': Comment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PinnedComment.objects.all().count(), 0)
