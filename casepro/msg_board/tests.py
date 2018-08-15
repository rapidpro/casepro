from django.urls import reverse
from django_comments.forms import CommentForm
from temba_client.utils import format_iso8601

from casepro.msg_board.models import MessageBoardComment
from casepro.test import BaseCasesTest


class CommentCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(CommentCRUDLTest, self).setUp()
        self.login(self.user1)

    def test_post_comment(self):
        data = CommentForm(self.unicef).generate_security_data()
        data.update({"name": "the supplied name", "comment": "Foo"})
        response = self.url_post("unicef", reverse("comments-post-comment"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)
        self.assertEqual(MessageBoardComment.objects.all().first().comment, "Foo")

    def test_list(self):
        data = CommentForm(self.unicef).generate_security_data()
        data.update({"comment": "Foo"})
        self.url_post("unicef", reverse("comments-post-comment"), data)

        data = CommentForm(self.unicef).generate_security_data()
        data.update({"comment": "Bar"})
        self.url_post("unicef", reverse("comments-post-comment"), data)

        response = self.url_get("unicef", reverse("msg_board.messageboardcomment_list"))

        comment1, comment2 = list(MessageBoardComment.objects.order_by("pk"))

        self.assertEqual(
            response.json,
            {
                "results": [
                    {
                        "id": comment2.pk,
                        "comment": "Bar",
                        "user": {"id": self.user1.pk, "name": "Evan"},
                        "submitted_on": format_iso8601(comment2.submit_date),
                        "pinned_on": None,
                    },
                    {
                        "id": comment1.pk,
                        "comment": "Foo",
                        "user": {"id": self.user1.pk, "name": "Evan"},
                        "submitted_on": format_iso8601(comment1.submit_date),
                        "pinned_on": None,
                    },
                ]
            },
        )

    def test_pin(self):
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({"name": "the supplied name", "comment": "Foo"})
        response = self.url_post(self.unicef, reverse("comments-post-comment"), data)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)
        response = self.url_post(
            self.unicef,
            reverse("msg_board.messageboardcomment_pin", kwargs={"pk": MessageBoardComment.objects.all().first().pk}),
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 1)

        response = self.url_get("unicef", reverse("msg_board.messageboardcomment_pinned"))
        self.assertEqual(len(response.json["results"]), 1)

    def test_unpin(self):
        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({"name": "the supplied name", "comment": "Foo"})
        response = self.url_post(self.unicef, reverse("comments-post-comment"), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)
        response = self.url_post(
            self.unicef,
            reverse("msg_board.messageboardcomment_pin", kwargs={"pk": MessageBoardComment.objects.all().first().pk}),
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 1)

        response = self.url_get("unicef", reverse("msg_board.messageboardcomment_pinned"))
        self.assertEqual(len(response.json["results"]), 1)

        response = self.url_post(
            self.unicef,
            reverse(
                "msg_board.messageboardcomment_unpin", kwargs={"pk": MessageBoardComment.objects.all().first().pk}
            ),
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(MessageBoardComment.get_all(self.unicef, pinned=True).count(), 0)

        response = self.url_get("unicef", reverse("msg_board.messageboardcomment_pinned"))
        self.assertEqual(len(response.json["results"]), 0)

    def test_pin_of_comment_in_another_org(self):
        self.login(self.admin)

        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.nyaruka).generate_security_data()
        data.update({"name": "the supplied name", "comment": "Foo"})
        response = self.url_post(self.nyaruka, reverse("comments-post-comment"), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)

        # pin in Unicef org
        response = self.url_post(
            self.unicef,
            reverse("msg_board.messageboardcomment_pin", kwargs={"pk": MessageBoardComment.objects.all().first().pk}),
        )
        self.assertEqual(response.status_code, 404)

    def test_unpin_invalid_comment(self):
        self.login(self.admin)

        self.assertEqual(MessageBoardComment.objects.all().count(), 0)
        data = CommentForm(target_object=self.unicef).generate_security_data()
        data.update({"name": "the supplied name", "comment": "Foo"})
        response = self.url_post(self.unicef, reverse("comments-post-comment"), data)
        self.assertEqual(MessageBoardComment.objects.all().count(), 1)

        # Pin in Nyaruka org
        response = self.url_post(
            self.unicef,
            reverse("msg_board.messageboardcomment_pin", kwargs={"pk": MessageBoardComment.objects.all().first().pk}),
        )
        self.assertEqual(response.status_code, 204)

        # Unpin in Unicef org
        response = self.url_post(self.unicef, reverse("msg_board.messageboardcomment_unpin", kwargs={"pk": 9999}))
        self.assertEqual(response.status_code, 404)
