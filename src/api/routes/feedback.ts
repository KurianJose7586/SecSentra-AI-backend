import { Router } from 'express';
import { AuthRequest, authenticateUser } from '../middlewares/auth';
import { successResponse, errorResponse } from '../utils/responseBuilder';
import { db } from '../../config';
import logger from '../utils/logger';

const router = Router();

router.post('/', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const { jobId, findingId, label, note } = req.body;
    const userId = req.user!.uid;

    if (!jobId || !findingId || !label) {
      return errorResponse(res, 'Missing required fields', 400);
    }

    if (!['correct', 'incorrect', 'unsure'].includes(label)) {
      return errorResponse(res, 'Invalid label value', 400);
    }

    const feedbackId = `feedback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const feedbackData = {
      feedbackId,
      jobId,
      findingId,
      userId,
      label,
      note: note || '',
      timestamp: new Date(),
    };

    await db.collection('feedback').doc(feedbackId).set(feedbackData);

    logger.info(`Feedback submitted: ${feedbackId} by user: ${userId}`);

    return successResponse(res, { feedbackId }, 'Feedback submitted successfully', 201);
  } catch (error: any) {
    logger.error('Feedback error:', error);
    return errorResponse(res, 'Failed to submit feedback', 500);
  }
});

export default router;