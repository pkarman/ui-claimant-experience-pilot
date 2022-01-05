# -*- coding: utf-8 -*-
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
import logging
import secrets
import os
from logindotgov.oidc import LoginDotGovOIDCClient, LoginDotGovOIDCError, IAL2, IAL1
from core.utils import session_as_dict, hash_idp_user_xid
from api.models import Claimant, IdentityProvider
from django.conf import settings
from api.whoami import WhoAmI

logger = logging.getLogger("logindotgov")

if os.environ.get("LOGIN_DOT_GOV_ENV") == "test":
    logindotgov_config = None
else:  # pragma: no cover
    logindotgov_config = LoginDotGovOIDCClient.discover()


def logindotgov_client():
    client = LoginDotGovOIDCClient(
        client_id=settings.LOGIN_DOT_GOV_CLIENT_ID,
        private_key=settings.LOGIN_DOT_GOV_PRIVATE_KEY,
        logger=logger,
    )
    if logindotgov_config:  # pragma: no cover
        client.config = logindotgov_config
    return client


@never_cache
def explain(request):
    if not settings.DEBUG:
        return JsonResponse({"error": "DEBUG is off"}, status=401)

    this_session = session_as_dict(request)
    return JsonResponse(this_session)


# if for any reason the claimant could not reach IAL2, they are redirected here.
@never_cache
def ial2required(request):
    # if we already have a verified session, redirect to frontend app
    if request.session.get("verified"):
        return redirect("/")

    return redirect("/ial2required/?idp=logindotgov")


@never_cache
def index(request):
    # if we already have a verified session, redirect to frontend app
    if request.session.get("verified"):
        return redirect("/")

    # stash selection
    if "swa" in request.GET:
        request.session["swa"] = request.GET["swa"]

    ial = 2
    if "ial" in request.GET and int(request.GET["ial"]) == 1:
        ial = 1
    request.session["IAL"] = ial

    # otherwise, initiate login.gov session
    # create our session with a "state" we can use to track IdP response.
    state = secrets.token_hex(11)
    nonce = secrets.token_hex(11)
    client = logindotgov_client()
    if ial == 2:
        scopes = settings.LOGIN_DOT_GOV_SCOPES
        acrs = IAL2
    else:
        scopes = ["openid", "email"]  # the most we can get
        acrs = IAL1

    login_url = client.build_authorization_url(
        state=state,
        nonce=nonce,
        redirect_uri=settings.LOGIN_DOT_GOV_REDIRECT_URI,
        acrs=acrs,
        scopes=scopes,
    )

    logger.debug("redirect {}".format(login_url))

    request.session["logindotgov"] = {"state": state, "nonce": nonce}

    return redirect(login_url)


# OIDC OP redirects here after auth attempt
@never_cache
def result(request):
    if "IAL" not in request.session:
        return redirect("/")

    client = logindotgov_client()
    try:
        auth_code, auth_state = client.validate_code_and_state(request.GET)
    except LoginDotGovOIDCError as error:
        logger.exception(error)
        return HttpResponse(error, status=403)

    logger.debug("code={} state={}".format(auth_code, auth_state))
    logger.debug("session: {}".format(session_as_dict(request)))
    if auth_state != request.session["logindotgov"]["state"]:
        logger.error("state mismatch")
        return HttpResponse("state mismatch", status=403)

    tokens = client.get_tokens(auth_code)

    # TODO check for error messages
    if "access_token" not in tokens:
        return HttpResponse(tokens, status=403)

    try:
        client.validate_tokens(
            tokens, request.session["logindotgov"]["nonce"], auth_code
        )
    except LoginDotGovOIDCError as error:
        logger.exception(error)
        return HttpResponse("Error exchanging token", status=403)

    userinfo = client.get_userinfo(tokens["access_token"])

    logindotgov_idp, _ = IdentityProvider.objects.get_or_create(name="login.gov")
    idp_user_xid = hash_idp_user_xid(userinfo["sub"])
    claimant, _ = Claimant.objects.get_or_create(
        idp_user_xid=idp_user_xid, idp=logindotgov_idp
    )

    request.session["verified"] = True
    request.session["logindotgov"]["userinfo"] = userinfo
    whoami = WhoAmI(
        IAL=request.session["IAL"],
        first_name=userinfo.get("given_name", ""),
        last_name=userinfo.get("family_name", ""),
        birthdate=userinfo.get("birthdate", ""),
        ssn=userinfo.get("social_security_number", ""),
        email=userinfo["email"],
        phone=userinfo.get("phone", ""),
        claimant_id=idp_user_xid,
    )
    request.session["whoami"] = whoami.as_dict()

    redirect_to = "/logindotgov/explain"
    if "redirect_to" in request.session:
        redirect_to = request.session["redirect_to"]
        del request.session["redirect_to"]
    logger.debug("redirect_to={}".format(redirect_to))

    return redirect(redirect_to)
