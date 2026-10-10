const { canTransition, missingDocuments } = require("../src/logic");

test("submitted can move to under_review", () => {
    expect(canTransition("submitted", "under_review")).toBe(true);
    });
    test("approved cannot go back", () => {
    expect(canTransition("approved", "submitted")).toBe(false);
    });
    test("cannot skip review", () => {
    expect(canTransition("submitted", "approved")).toBe(false);
    });
    test("reports missing documents", () => {
    expect(
        missingDocuments(["transcript", "proof_of_income"], ["transcript"]),
    ).toEqual(["proof_of_income"]);
});
