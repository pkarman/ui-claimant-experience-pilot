import { Fieldset } from "@trussworks/react-uswds";
import { FieldArray, useFormikContext } from "formik";
import { ClaimSchemaField } from "../../../common/YupBuilder";
import * as yup from "yup";
import i18next from "i18next";

import { Name } from "../Name/Name";
import { YesNoRadio } from "../YesNoRadio/YesNoRadio";

export const CLAIMANT_NAMES_SCHEMA_FIELDS: ClaimSchemaField[] = [
  "claimant_name",
  "alternate_names",
];

export const CLAIMANT_NAMES_ADDITIONAL_VALIDATIONS = {
  claimant_has_alternate_names: yup
    .string()
    .required(i18next.t("validation.required")),
};

const BLANK_PERSON_NAME: PersonName = {
  first_name: "",
  middle_name: "",
  last_name: "",
};

export const ClaimantNames = () => {
  const { values } = useFormikContext<Claim>();
  return (
    <>
      <Fieldset legend="Legal Name">
        <Name id="claimant_name" name="claimant_name" />
      </Fieldset>
      <br />
      <Fieldset legend="In the past 18 months, have you worked under a name different from above?">
        <YesNoRadio
          id="claimant_has_alternate_names"
          name="claimant_has_alternate_names"
        />
      </Fieldset>
      <br />
      {values.claimant_has_alternate_names === "yes" && (
        <Fieldset legend="Alternate Name">
          <FieldArray
            name="alternate_names"
            render={() => {
              values.alternate_names?.length === 0 &&
                values.alternate_names.push(BLANK_PERSON_NAME);
              return values.alternate_names?.map((alternateName, index) => {
                const name = `alternate_names.${index}`;
                return <Name key={name} id={name} name={name} />;
              });
            }}
          />
        </Fieldset>
      )}
    </>
  );
};
