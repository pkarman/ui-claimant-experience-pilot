import { ComponentMeta, ComponentStory } from "@storybook/react";
import { Formik, Form } from "formik";

import {
  DemographicInformation,
  DemographicInformationPage,
} from "./DemographicInformation";
import YupBuilder from "../../../common/YupBuilder";
import { noop } from "../../../testUtils/noop";

export default {
  title: "Pages/Demographic Information",
  component: DemographicInformation,
} as ComponentMeta<typeof DemographicInformation>;

const Template: ComponentStory<typeof DemographicInformation> = () => {
  const validationSchema = YupBuilder(
    "claim-v1.0",
    DemographicInformationPage.schemaFields
  );

  const initialValues = {
    birthdate: new Date(2001, 11, 21).toDateString(),
    sex: undefined,
    ethnicity: undefined,
    race: [],
    education_level: undefined,
  };

  return (
    <Formik
      initialValues={initialValues}
      validationSchema={validationSchema}
      onSubmit={noop}
    >
      <Form>
        <DemographicInformation />
      </Form>
    </Formik>
  );
};

export const Default = Template.bind({});
