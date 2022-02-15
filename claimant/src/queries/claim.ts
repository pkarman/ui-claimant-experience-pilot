import { useMutation, useQuery } from "react-query";
import Cookies from "universal-cookie";
import httpclient from "../utils/httpclient";
import axios from "axios";

const COMPLETED_CLAIM_ENDPOINT = "/api/completed-claim/";
const PARTIAL_CLAIM_ENDPOINT = "/api/partial-claim/";

const getPartialClaim = async () => {
  try {
    const { data } = await httpclient.get<Claim>(PARTIAL_CLAIM_ENDPOINT, {
      withCredentials: true,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        // no partial claim exists, which is completely normal
        const emptyClaim: Partial<Claim> = {};
        return emptyClaim;
      } else {
        throw error;
      }
    } else {
      throw error;
    }
  }
};

const submitClaim = (payload: Claim) => {
  const cookies = new Cookies();
  const csrftoken = cookies.get("csrftoken");
  const url = payload.is_complete
    ? COMPLETED_CLAIM_ENDPOINT
    : PARTIAL_CLAIM_ENDPOINT;
  return httpclient.post<ClaimResponse>(url, payload, {
    withCredentials: true,
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json",
    },
  });
};

const getCompletedClaim = () => {
  return httpclient.get(COMPLETED_CLAIM_ENDPOINT, { withCredentials: true });
};

export const useSubmitClaim = () => {
  return useMutation((payload: Claim) => submitClaim(payload));
};

export const useGetPartialClaim = () => {
  return useQuery("partial-claim", () => getPartialClaim());
};

export const useGetCompletedClaim = () => {
  return useQuery("getCompletedClaim", () => getCompletedClaim());
};
