def user(request):
    """
    Context processor that adds boolean of whether current user is an admin for current org
    """
    if request.user.is_anonymous or not request.org:
        is_admin = False
        partner = None
        is_faq_only = True
    else:
        is_admin = request.user.can_administer(request.org)
        partner = request.user.get_partner(request.org)
        is_faq_only = request.user.must_use_faq()

    return {"user_is_admin": is_admin, "user_partner": partner, "user_is_faq_only": is_faq_only}
