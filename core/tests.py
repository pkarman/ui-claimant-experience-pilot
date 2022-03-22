# -*- coding: utf-8 -*-
from unittest.mock import patch
import boto3
from botocore.stub import Stubber
from django.test import TestCase, Client
from django.core import mail
from django.template.loader import render_to_string
from core.tasks_tests import CeleryTestCase

from api.test_utils import create_idp, create_swa, create_claimant
from api.models import Claim, SWA

from .claim_storage import ClaimWriter, ClaimReader, ClaimStore
from jwcrypto import jwe, jwk
from jwcrypto.common import json_encode, json_decode
from .claim_encryption import (
    PackagedClaim,
    ALG as EncryptionALG,
    ENC as EncryptionENC,
    AsymmetricClaimEncryptor,
    AsymmetricClaimDecryptor,
    SymmetricClaimEncryptor,
    SymmetricClaimDecryptor,
    RotatableSymmetricClaimDecryptor,
    SymmetricKeyRotator,
    symmetric_encryption_key,
)
from .test_utils import (
    create_s3_bucket,
    delete_s3_bucket,
    generate_keypair,
    generate_symmetric_encryption_key,
)
from .exceptions import SwaXidError
import logging
from core.email import Email, InitialClaimConfirmationEmail
from core.swa_xid import SwaXid


logger = logging.getLogger(__name__)


class CoreTestCase(TestCase):
    def setUp(self):
        # Empty the test outbox
        mail.outbox = []

    def test_claimant_page(self):
        response = self.client.get("/claimant/")
        self.assertContains(response, "Unemployment Insurance Claim", status_code=200)

    def test_email(self):
        to = "fake@example.com"
        Email(to=to, subject="test", body="hello world").send()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "test")

    def test_404(self):
        resp = self.client.get("/route-that-does-not-exist")
        self.assertContains(resp, "Page not found", status_code=404)

    def test_500(self):
        c = Client(raise_request_exception=False)
        resp = c.get("/500/")
        self.assertContains(resp, "Sorry, we had a problem", status_code=500)

    def test_live(self):
        response = self.client.get("/live/")
        live_resp = response.json()
        self.assertTrue(live_resp["db"])
        self.assertTrue(live_resp["redis"])
        self.assertGreaterEqual(float(live_resp["db_response"]), 0)
        self.assertLess(float(live_resp["db_response"]), 1)
        self.assertGreaterEqual(float(live_resp["redis_response"]), 0)
        self.assertLess(float(live_resp["redis_response"]), 1)
        # celery not running in this test case, but we want to verify the key exists.
        self.assertFalse(live_resp["celery"])
        # status is 503 because celery is offline
        self.assertEqual(response.status_code, 503)


class BucketableTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_s3_bucket()
        create_s3_bucket(is_archive=True)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        delete_s3_bucket()
        delete_s3_bucket(is_archive=True)


class CoreClaimStorageTestCase(BucketableTestCase):
    def test_claim_writer(self):
        idp = create_idp()
        swa, _ = create_swa()
        claimant = create_claimant(idp)
        claim = Claim(claimant=claimant, swa=swa)
        claim.save()

        cw = ClaimWriter(claim, "test payload")
        self.assertTrue(cw.write())
        self.assertEqual(
            claim.events.filter(category=Claim.EventCategories.STORED).count(), 1
        )

        cr = ClaimReader(claim)
        bucket_asset = cr.read()
        self.assertEqual(bucket_asset, "test payload")

        # explicit path declaration
        cw = ClaimWriter(claim, "test path", "path/to/my/object")
        self.assertTrue(cw.write())
        self.assertEqual(
            claim.events.filter(category=Claim.EventCategories.STORED).count(), 2
        )

        cr = ClaimReader(claim, "path/to/my/object")
        bucket_asset = cr.read()
        self.assertEqual(bucket_asset, "test path")

    def test_claim_writer_with_sym_encryption(self):
        key = symmetric_encryption_key()
        idp = create_idp()
        swa, _ = create_swa()
        claimant = create_claimant(idp)
        claim = Claim(claimant=claimant, swa=swa)
        claim.save()
        claim_payload = {
            "id": str(claim.uuid),
            "foo": "something-really-private-and-sensitive",
        }
        ce = SymmetricClaimEncryptor(claim_payload, key)
        packaged_claim = ce.packaged_claim()
        cw = ClaimWriter(claim, packaged_claim.as_json())
        self.assertTrue(cw.write())

        cr = ClaimReader(claim)
        packaged_claim_str = cr.read()
        cd = SymmetricClaimDecryptor(packaged_claim_str, key)
        decrypted_claim = cd.decrypt()
        self.assertEqual(decrypted_claim, claim_payload)

    def test_claim_storage_exceptions(self):
        with self.assertRaises(ValueError) as context:
            ClaimWriter(True, True)
        self.assertIn("Must provide path or a Claim object", str(context.exception))

        with self.assertRaises(ValueError) as context:
            ClaimReader(True)
        self.assertIn("Must provide path or a Claim object", str(context.exception))

        self.assertFalse(ClaimReader(Claim(), "no/path").read())

    @patch("core.claim_storage.ClaimStore.s3_client")
    def test_claim_writer_error(self, mock_boto3_client):
        idp = create_idp()
        swa, _ = create_swa()
        claimant = create_claimant(idp)
        claim = Claim(claimant=claimant, swa=swa)
        claim.save()

        client = boto3.client("s3")
        stubber = Stubber(client)
        stubber.add_client_error("put_object")
        stubber.activate()
        mock_boto3_client.return_value = client

        cw = ClaimWriter(claim, "test payload")
        self.assertFalse(cw.write())

    @patch("core.claim_storage.ClaimStore.bucket")
    def test_claim_storage_delete_error(self, mock_boto3_bucket):
        idp = create_idp()
        swa, _ = create_swa()
        claimant = create_claimant(idp)
        claim = Claim(claimant=claimant, swa=swa)
        claim.save()

        bucket = boto3.resource("s3").Bucket("no-such-bucket")
        stubber = Stubber(bucket.meta.client)
        stubber.add_client_error("delete_objects")
        stubber.activate()
        mock_boto3_bucket.return_value = bucket

        cs = ClaimStore()
        self.assertFalse(cs.delete("foo"))


class CoreClaimEncryptionTestCase(TestCase):
    def test_asymmetric_claim_encryptor(self):
        private_key_jwk, public_key_jwk = generate_keypair()
        claim = {"id": "123-abc", "foo": "something-really-private-and-sensitive"}
        ce = AsymmetricClaimEncryptor(claim, public_key_jwk)
        self.assertEqual(ce.protected_header()["alg"], EncryptionALG)
        self.assertEqual(ce.protected_header()["enc"], EncryptionENC)
        packaged_claim = ce.packaged_claim()
        self.assertIsInstance(
            packaged_claim, PackagedClaim, "object is a PackagedClaim"
        )

        claim_dict = packaged_claim.as_dict()
        self.assertEqual(claim_dict["claim_id"], "123-abc")
        self.assertNotIn("foo", claim_dict["claim"]["ciphertext"])
        self.assertNotIn(
            "something-really-private-and-sensitive",
            claim_dict["claim"]["ciphertext"],
        )

        # round-trip: decrypt
        jwetoken = jwe.JWE()
        jwetoken.deserialize(json_encode(claim_dict["claim"]), key=private_key_jwk)
        decrypted_claim = json_decode(jwetoken.payload)
        self.assertEqual(decrypted_claim, claim)

        # allows for PEM key as bytes or str
        private_key_pem = private_key_jwk.export_to_pem(True, None)
        public_key_pem = public_key_jwk.export_to_pem()

        ce = AsymmetricClaimEncryptor(claim, public_key_pem)
        packaged_claim = ce.packaged_claim()
        cd = AsymmetricClaimDecryptor(packaged_claim.as_json(), private_key_pem)
        decrypted_claim = cd.decrypt()
        self.assertEqual(decrypted_claim["id"], "123-abc")

        ce = AsymmetricClaimEncryptor(claim, public_key_pem.decode("utf-8"))
        packaged_claim = ce.packaged_claim()
        cd = AsymmetricClaimDecryptor(
            packaged_claim.as_json(), private_key_pem.decode("utf-8")
        )
        decrypted_claim = cd.decrypt()
        self.assertEqual(decrypted_claim["id"], "123-abc")

    def test_symmetric_claim_encryptor(self):
        key = jwk.JWK(generate="oct", size=256)
        claim = {"id": "123-abc", "foo": "something-really-private-and-sensitive"}
        ce = SymmetricClaimEncryptor(claim, key)
        packaged_claim = ce.packaged_claim()
        self.assertIsInstance(
            packaged_claim, PackagedClaim, "object is a PackagedClaim"
        )

        claim_dict = packaged_claim.as_dict()
        self.assertEqual(claim_dict["claim_id"], "123-abc")
        self.assertNotIn("foo", claim_dict["claim"]["ciphertext"])
        self.assertNotIn(
            "something-really-private-and-sensitive",
            claim_dict["claim"]["ciphertext"],
        )

        # round-trip: decrypt
        cd = SymmetricClaimDecryptor(packaged_claim.as_json(), key)
        decrypted_claim = cd.decrypt()
        self.assertEqual(decrypted_claim, claim)

    def test_symmetric_key_rotation(self):
        old_key = symmetric_encryption_key()
        new_key = symmetric_encryption_key(generate_symmetric_encryption_key())
        rotator = SymmetricKeyRotator(old_key=old_key, new_key=new_key)

        claim = {"id": "123-abc", "foo": "something-really-private-and-sensitive"}

        ce = SymmetricClaimEncryptor(claim, old_key)
        packaged_claim = ce.packaged_claim()
        repackaged_claim = rotator.rotate(packaged_claim)
        self.assertNotEqual(packaged_claim, repackaged_claim)

        cd = SymmetricClaimDecryptor(repackaged_claim.as_json(), new_key)
        decrypted_repackaged_claim = cd.decrypt()
        self.assertEqual(decrypted_repackaged_claim, claim)

    def test_transparent_key_rotation_decryption(self):
        list_of_keys = [
            generate_symmetric_encryption_key(),
            generate_symmetric_encryption_key(),
        ]
        claim = {"id": "123-abc", "foo": "something-really-private-and-sensitive"}
        ce = SymmetricClaimEncryptor(claim, symmetric_encryption_key(list_of_keys[1]))
        packaged_claim = ce.packaged_claim()

        rotable_decryptor = RotatableSymmetricClaimDecryptor(
            packaged_claim.as_json(), list_of_keys
        )
        decrypted_packaged_claim = rotable_decryptor.decrypt()
        self.assertEqual(decrypted_packaged_claim, claim)

        # wrong key should raise error
        with self.assertRaises(ValueError):
            sd = SymmetricClaimDecryptor(
                packaged_claim.as_json(), symmetric_encryption_key(list_of_keys[0])
            )
            sd.decrypt()

        with self.assertRaises(ValueError):
            rotable_decryptor = RotatableSymmetricClaimDecryptor(
                packaged_claim.as_json(), [generate_symmetric_encryption_key()]
            )
            rotable_decryptor.decrypt()


class EmailTestCase(CeleryTestCase):
    def setUp(self):
        super().setUp()
        # Empty the test outbox
        mail.outbox = []

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_initial_claim_confirmation_email(self):
        claim = Claim(
            uuid="1234", swa=SWA(name="Some State", claimant_url="www.mystateswa.com")
        )
        email_address = "fake@example.com"
        email = InitialClaimConfirmationEmail(claim, email_address)
        email.send_later()
        # this requires celery task to run to completion async,
        # so wait a little
        self.wait_for_workers_to_finish()
        email_body = render_to_string(
            "emails/claim_confirmation_email.txt",
            {"swa": claim.swa, "claim_id": claim.uuid},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your UI Claim receipt")
        self.assertTemplateUsed(template_name="emails/claim_confirmation_email.txt")
        self.assertEqual(email_body, mail.outbox[0].body)
        # ensure the variables are rendering
        self.assertIn(
            "Your claim has been forwarded to Some State", mail.outbox[0].body
        )


class LaunchDarklyTestCase(TestCase):
    def test_client_key_populated(self):
        response = self.client.get("/claimant/")
        self.assertRegex(
            response.content.decode("UTF-8"), r'window\.LD_CLIENT_SDK_KEY=".{24}"'
        )

    @patch("core.middleware.maintenance_mode.ld_client")
    def test_maintenance_mode(self, patched_ld_client_core):
        patched_ld_client_core.variation.return_value = True
        response = self.client.get("/home/")
        self.assertContains(response, "down for maintenance")


class SwaXidTestCase(TestCase):
    def test_swa_xid_timestamp(self):
        sx = SwaXid("20220222-123456-abc", "AR")
        # converts to UTC
        self.assertEqual(sx.as_isoformat(), "2022-02-22T18:34:56+00:00")
        self.assertTrue(sx.datetime)
        self.assertEqual(f"{sx}", "20220222-123456-abc")
        # however the format is incorrect
        self.assertFalse(sx.format_ok())

    def test_swa_xid_format(self):
        sx = SwaXid("20220222-123456-1234567-123456789", "AR")
        self.assertTrue(sx.format_ok())

    def test_swa_xid_setting_unknown(self):
        sx = SwaXid("abc-123", "XX")
        self.assertTrue(sx.format_ok())
        self.assertFalse(sx.datetime)
        self.assertFalse(sx.as_isoformat())

    def test_swa_xid_invalid_date(self):
        sx = SwaXid("20220222-999999-abc", "AR")
        self.assertFalse(sx.format_ok())
        self.assertFalse(sx.datetime)


class CoreExceptionsTestCase(TestCase):
    def test_swa_xid_error(self):
        swa, _ = create_swa()
        err = SwaXidError(swa, "oops!")
        self.assertEqual(err.swa, swa)
