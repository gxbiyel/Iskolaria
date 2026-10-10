const TRANSITIONS = {
    submitted: ['under_review'],
    under_review: ['approved', 'rejected', 'waitlisted'],
    waitlisted: ['approved', 'rejected'],
    approved: [],
    rejected: [],
};

function canTransition(from, to) {
    return (TRANSITIONS[from] || []).includes(to);
}

function missingDocuments(required, uploaded) {
    return required.filter((d) => !uploaded.includes(d));
}

module.exports = { canTransition, missingDocuments };