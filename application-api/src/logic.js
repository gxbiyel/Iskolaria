const TRANSITIONS = {
    submitted: ['under_review'],
    under_review: ['approved', 'rejected', 'waitlisted'],
    waitlisted: ['approved', 'rejected'],
    approved: ['removed'],
    rejected: [],
    removed: [],
    cancelled: [],
};

// Statuses from which a student may cancel their own application
const CANCELLABLE = ["submitted", "under_review", "waitlisted"];

function canTransition(from, to) {
    return (TRANSITIONS[from] || []).includes(to);
}

function canCancel(status) {
    return CANCELLABLE.includes(status);
}

function missingDocuments(required, uploaded) {
    return required.filter((d) => !uploaded.includes(d));
}

module.exports = { canTransition, canCancel, missingDocuments };
