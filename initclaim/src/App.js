import React, { useState } from 'react'
import PropTypes from 'prop-types';

import {
  BrowserRouter as Router,
  Switch,
  Route,
  NavLink,
  Link,
} from 'react-router-dom';

import '@trussworks/react-uswds/lib/uswds.css';
import '@trussworks/react-uswds/lib/index.css';
import {
  GovBanner,
  Header,
  Title,
  NavMenuButton,
  PrimaryNav,
  GridContainer,
} from '@trussworks/react-uswds';

import { Routes } from './routes';
import WhoAmIPage from './pages/whoami';
import withClaimant from './hoc/with-claimant';

import './App.css';

function App(props) {
  const { currentClaimant } = props;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { HOME_PAGE, WHOAMI_PAGE, } = Routes

  const toggleMobileNav = () => {
    setMobileNavOpen((prevOpen) => !prevOpen)
  };

  const navItems = [
    <NavLink to={HOME_PAGE} key={HOME_PAGE} activeClassName="usa-current" exact>
      Home
    </NavLink>,
    <NavLink to={WHOAMI_PAGE} key={WHOAMI_PAGE} activeClassName="usa-current">
      Who am I
    </NavLink>,
  ];

  return (
    <Router basename="/initclaim">
      <GovBanner />
      <Header basic>
        <div className="usa-nav-container">
          <div className="usa-navbar">
            <Title>
              <Link to={HOME_PAGE}>Example Application</Link>
            </Title>
            <NavMenuButton
              label="Menu"
              onClick={toggleMobileNav}
              className="usa-menu-btn"
            />
          </div>

          <PrimaryNav
            aria-label="Primary navigation"
            items={navItems}
            onToggleMobileNav={toggleMobileNav}
            mobileExpanded={mobileNavOpen}
          />
        </div>
      </Header>

      <section className="usa-section">
        <GridContainer>
          <Switch>
            <Route path={WHOAMI_PAGE}>
              <WhoAmIPage whoami={currentClaimant} />
            </Route>
            <Route path={HOME_PAGE}>
            </Route>
          </Switch>
        </GridContainer>
      </section>
    </Router>
  );
}

export default withClaimant(App);

App.propTypes = {
  currentClaimant: PropTypes.oneOfType([
    PropTypes.bool,
    PropTypes.object,
  ]),
};
