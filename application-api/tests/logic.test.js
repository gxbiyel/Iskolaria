const { canTransition, canCancel, missingDocuments } = require("../src/logic");

// ---- original tests ----
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

// ---- remove from scholarship ----
test("admin can remove an approved student", () => {
    expect(canTransition("approved", "removed")).toBe(true);
});

test("cannot remove a student before approval", () => {
    expect(canTransition("submitted", "removed")).toBe(false);
    expect(canTransition("under_review", "removed")).toBe(false);
});

test("removed is final", () => {
    expect(canTransition("removed", "approved")).toBe(false);
});

// ---- student cancel ----
test("student can cancel while pending", () => {
    expect(canCancel("submitted")).toBe(true);
    expect(canCancel("under_review")).toBe(true);
    expect(canCancel("waitlisted")).toBe(true);
});

test("student cannot cancel once approved", () => {
    expect(canCancel("approved")).toBe(false);
});

test("student cannot cancel a rejected application", () => {
    expect(canCancel("rejected")).toBe(false);
});