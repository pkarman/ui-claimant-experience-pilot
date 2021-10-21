// Run the pa11y and Lighthouse audits
/* eslint-disable no-undef */
context("Cypress Audit", { scrollBehavior: false }, () => {
  it("passes pa11y checks", () => {
    // mock the authn flow for 508 checks
    cy.mock_login();

    cy.visit("/claimant/");
    cy.url().should("not.include", "/idp/?redirect_to");

    // run the 508 checks
    cy.pa11y({
      runners: ["htmlcs"],
      standard: "WCAG2AA",
    });
  });

  it("passes lighthouse checks", () => {
    // mock the authn flow
    cy.mock_login();

    cy.visit("/claimant/");
    cy.url().should("not.include", "/idp/?redirect_to");

    // performance tests
    const thresholds = {
      performance: 75,
      accessibility: 100,
    };
    const options = {};
    const config = {
      extends: "lighthouse:default",
      settings: {
        onlyCategories: ["performance", "accessibility"],
        skipAudits: [
          "installable-manifest",
          "splash-screen",
          "themed-omnibox",
          "mainthread-work-breakdown",
          "network-requests",
          "main-thread-tasks",
          "js-libraries",
        ],
      },
    };
    cy.lighthouse(thresholds, options, config);
  });
});
