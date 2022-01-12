import { Fieldset } from "@trussworks/react-uswds";
import { useTranslation } from "react-i18next";
import { useFormikContext } from "formik";
import { TextField } from "../../../components/form/fields/TextField/TextField";
import { ClaimSchemaField } from "../../../common/YupBuilder";

import { IPageDefinition } from "../../PageDefinitions";
import { BooleanRadio } from "../../../components/form/BooleanRadio/BooleanRadio";
import { CheckboxField } from "../../../components/form/fields/CheckboxField/CheckboxField";
import { PhoneNumberField } from "../../../components/form/PhoneNumberField/PhoneNumberField";

const schemaFields: ClaimSchemaField[] = [
  "phones",
  "LOCAL_more_phones",
  "interpreter_required",
  "preferred_language",
];

export const ContactInformation = () => {
  const { t } = useTranslation("claimForm", {
    keyPrefix: "contact_information",
  });
  const { values } = useFormikContext<ClaimantInput>();

  return (
    <>
      <Fieldset legend={t("what_is_your_contact_information")}>
        <PhoneNumberField id="phones[0]" name="phones[0]" showSMS={false} />
        <CheckboxField
          id="LOCAL_more_phones"
          name="LOCAL_more_phones"
          data-testid="LOCAL_more_phones"
          label={t("more_phones")}
        />
        {values.LOCAL_more_phones && (
          <PhoneNumberField id="phones[1]" name="phones[1]" showSMS={false} />
        )}
      </Fieldset>
      <Fieldset legend={t("interpreter_required.label")}>
        <BooleanRadio id="interpreter_required" name="interpreter_required" />
      </Fieldset>
      <TextField
        label={t("preferred_language.label")}
        id={"preferred_language"}
        name={"preferred_language"}
        type="text"
      />
    </>
  );
};

export const ContactInformationPage: IPageDefinition = {
  path: "contact-information",
  heading: "contact_information",
  schemaFields: schemaFields,
  initialValues: {
    phones: [],
    LOCAL_more_phones: undefined,
    interpreter_required: undefined,
    preferred_language: "",
  },
  Component: ContactInformation,
};
