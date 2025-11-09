import { Router } from 'express';
import { AuthRequest, authenticateUser } from '../middlewares/auth';
import { errorResponse } from '../utils/responseBuilder';
import { db } from '../../config';
import logger from '../utils/logger';

const router = Router();

router.get('/:jobId', authenticateUser, async (req: AuthRequest, res) => {
  try {
    const { jobId } = req.params;
    const { format } = req.query;
    const userId = req.user!.uid;

    const jobDoc = await db.collection('jobs').doc(jobId).get();

    if (!jobDoc.exists) {
      return errorResponse(res, 'Job not found', 404);
    }

    const jobData = jobDoc.data();

    if (jobData?.userId !== userId) {
      return errorResponse(res, 'Unauthorized access', 403);
    }

    if (format === 'json') {
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Content-Disposition', `attachment; filename="report_${jobId}.json"`);
      return res.send(JSON.stringify(jobData, null, 2));
    }

    return errorResponse(res, 'PDF export not yet implemented', 501);
  } catch (error: any) {
    logger.error('Export error:', error);
    return errorResponse(res, 'Failed to export report', 500);
  }
});

export default router;