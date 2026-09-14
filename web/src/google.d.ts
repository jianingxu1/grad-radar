interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentityServices {
  initialize(configuration: {
    callback: (response: GoogleCredentialResponse) => void;
    client_id: string;
    nonce: string;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      shape: "rectangular" | "pill" | "circle" | "square";
      size: "large";
      text: "sign_in" | "continue_with";
      theme: "outline";
      width: number;
    },
  ): void;
}

interface Window {
  google?: { accounts: { id: GoogleIdentityServices } };
}
