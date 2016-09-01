from casepro.test import BaseCasesTest
from django.core.urlresolvers import reverse
from django_comments.forms import CommentForm
from casepro.msg_board.models import MessageBoardComment


class CommentTest(BaseCasesTest):
    def setUp(self):
        super(CommentTest, self).setUp()
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
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)
        self.assertEqual(MessageBoardComment.objects.all().first().comment, 'Foo')

    def test_comment_list_view(self):
        data = CommentForm(self.unicef).generate_security_data()
        data.update({'name': 'first name', 'comment': 'Foo'})
        self.url_post('unicef', reverse('comments-post-comment'), data)

        data = CommentForm(self.unicef).generate_security_data()
        data.update({'name': 'second name', 'comment': 'Bar'})
        self.url_post('unicef', reverse('comments-post-comment'), data)

        response = self.url_get('unicef', reverse('msg_board.messageboardcomment_list'))
        results = response.json['results']

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['comment'], 'Bar')
        self.assertEqual(results[0]['user_name'], 'second name')

        self.assertEqual(results[1]['comment'], 'Foo')
        self.assertEqual(results[1]['user_name'], 'first name')

    def test_pin_comment(self):
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.unicef,
            reverse('comments-post-comment'), data)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_pin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 1)

        response = self.url_get('unicef', reverse('msg_board.messageboardcomment_pinned'))
        self.assertEqual(len(response.json['results']), 1)

        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_pin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_unpin_comment(self):
        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.unicef,
            reverse('comments-post-comment'), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_pin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 1)

        response = self.url_get('unicef', reverse('msg_board.messageboardcomment_pinned'))
        self.assertEqual(len(response.json['results']), 1)

        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_unpin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)

        response = self.url_get('unicef', reverse('msg_board.messageboardcomment_pinned'))
        self.assertEqual(len(response.json['results']), 0)

        # Trying to unpin an unpinned comment does nothing
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_unpin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_pin_of_comment_in_another_org(self):
        self.login(self.admin)

        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.nyaruka).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.nyaruka,
            reverse('comments-post-comment'), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)

        # pin in Unicef org
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_pin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_unpin_invalid_comment(self):
        self.login(self.admin)

        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({
            'name': 'the supplied name',
            'comment': 'Foo'
        })
        response = self.url_post(
            self.unicef,
            reverse('comments-post-comment'), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)

        # Pin in Nyaruka org
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_pin', kwargs={'pk': MessageBoardComment.objects.all().first().pk})
        )
        self.assertEqual(response.status_code, 204)

        # Unpin in Unicef org
        response = self.url_post(
            self.unicef,
            reverse('msg_board.messageboardcomment_unpin', kwargs={'pk': 9999})
        )
        self.assertEqual(response.status_code, 404)
