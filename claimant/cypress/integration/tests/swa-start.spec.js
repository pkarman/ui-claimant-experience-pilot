import faker from "@faker-js/faker";

/* eslint-disable no-undef */

context("SWA start page", { scrollBehavior: "center" }, () => {
  it("redirects to /start/ on happy path answers", () => {
    cy.visit("/start/XX/");
    cy.click_yes("use-app");
    cy.click_next();
    cy.url().should("contain", "/start/");
    cy.url().should("contain", "swa=XX");
  });

  it("requires radio selection to proceed", () => {
    cy.visit("/start/XX/");
    cy.click_next();
    cy.contains("Correct the error on this page");
    cy.url().should("contain", "/start/XX/");
  });

  it("shows 404 when SWA code is not active", () => {
    cy.request({ url: "/start/oops/", failOnStatusCode: false })
      .its("status")
      .should("equal", 404);
  });

  it("redirects to SWA site redirection page on unhappy path answers", () => {
    cy.visit("/start/XX/");
    cy.click_no("use-app");
    // cypress cannot access other domains so do not click Next, just check that form.action has changed
    cy.get("#use-app-form")
      .invoke("attr", "action")
      .should("contain", "swa-redirect/XX");
  });

  it("shows/hides error message(s) on form validation", () => {
    cy.visit("/start/XX/");
    cy.click_next();
    cy.contains("Correct the error on this page");
    cy.contains("This field is required");
    cy.get("span").filter(".usa-error-message");
    cy.get("div").filter(".usa-alert--error");
    cy.click_yes("use-app");
    cy.get("span").not(".usa-error-message");
    cy.get("div").not(".usa-alert--error");
  });

  context("IDENTITY_ONLY featureset", () => {
    it("uses verify identity language", () => {
      cy.visit("/start/YY/");
      cy.contains("Verify your identity online with Login.gov").should(
        "be.visible"
      );
      cy.click_yes("use-app");
      cy.click_next();
      cy.url().should("contain", "/idp/YY/");
    });
  });

  context("swa_xid param", () => {
    it("should preserve optional swa_xid param", () => {
      const swa_xid = faker.datatype.uuid();
      cy.visit(`/start/YY/?swa_xid=${swa_xid}`);
      cy.click_yes("use-app");
      cy.click_next();
      cy.url().should("contain", "/idp/YY/?");
      cy.url().should("contain", `swa_xid=${swa_xid}`);
      cy.getCookie("swa_xid").should("have.property", "value", swa_xid);
    });

    it("filters out dangerous characters", () => {
      const swa_xid = "abc123-<alert>danger!</alert>";
      cy.visit(`/start/YY/?swa_xid=${swa_xid}`);
      cy.click_yes("use-app");
      cy.click_next();
      cy.url().should("contain", "/idp/YY/?");
      cy.url().should("contain", "swa_xid=abc123-alertdangeralert");
    });
  });
});
