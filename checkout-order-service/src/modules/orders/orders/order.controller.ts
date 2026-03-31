import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
  HttpStatus,
} from '@nestjs/common'
import { InjectRepository } from '@nestjs/typeorm'
import { Repository } from 'typeorm'
import { Order } from './order.entity'
import { OrderQueryDto } from './dto/order-query.dto'
import { CancelOrderDto } from './dto/cancel-order.dto'
import { ReturnOrderDto } from './dto/return-order.dto'
import { OrderService } from './order.service'
import { CommerceException, CommerceErrorCodes } from '../../../shared/errors/commerce.exception'

@Controller('commerce/orders')
export class OrderController {
  constructor(
    @InjectRepository(Order)
    private readonly orderRepo: Repository<Order>,
    private readonly orderService: OrderService,
  ) {}

  @Get()
  async listOrders(@Query() query: OrderQueryDto): Promise<{ data: Order[]; nextCursor: string | null }> {
    const limit = query.limit ?? 20

    let cursorDate: Date | undefined
    let cursorId: string | undefined

    if (query.cursor) {
      const decoded = Buffer.from(query.cursor, 'base64').toString('utf8')
      const [dateStr, id] = decoded.split(':')
      cursorDate = new Date(dateStr)
      cursorId = id
    }

    const qb = this.orderRepo
      .createQueryBuilder('order')
      .where('order.customerId = :customerId', { customerId: query.customerId })
      .orderBy('order.createdAt', 'DESC')
      .addOrderBy('order.orderId', 'DESC')
      .take(limit + 1)

    if (cursorDate && cursorId) {
      qb.andWhere(
        '(order.createdAt < :cursorDate OR (order.createdAt = :cursorDate AND order.orderId < :cursorId))',
        { cursorDate, cursorId },
      )
    }

    const rows = await qb.getMany()

    let nextCursor: string | null = null
    if (rows.length > limit) {
      rows.pop()
      const last = rows[rows.length - 1]
      nextCursor = Buffer.from(`${last.createdAt.toISOString()}:${last.orderId}`).toString('base64')
    }

    return { data: rows, nextCursor }
  }

  @Get(':id')
  async getOrder(
    @Param('id') id: string,
    @Query() query: OrderQueryDto,
  ): Promise<Order> {
    const order = await this.orderRepo.findOne({
      where: { orderId: id },
      relations: ['statusHistory'],
    })

    if (!order) {
      throw new CommerceException(
        CommerceErrorCodes.NOT_FOUND,
        `Order ${id} not found`,
        HttpStatus.NOT_FOUND,
      )
    }

    if (order.customerId !== query.customerId) {
      throw new CommerceException(
        CommerceErrorCodes.NOT_FOUND,
        `Order ${id} not found`,
        HttpStatus.NOT_FOUND,
      )
    }

    return order
  }

  /**
   * POST /commerce/orders/:id/cancel
   * Cancels a processing order. Returns 422 for fulfilled orders (Requirement 8.1, 8.2).
   */
  @Post(':id/cancel')
  async cancelOrder(
    @Param('id') id: string,
    @Body() body: CancelOrderDto,
    @Query() query: OrderQueryDto,
  ): Promise<Order> {
    const customerId = body.customerId ?? query.customerId
    return this.orderService.cancelOrder(id, customerId, body.reason)
  }

  /**
   * POST /commerce/orders/:id/return
   * Requests a return for a fulfilled order. Returns 422 for non-fulfilled orders (Requirement 8.3, 8.4).
   */
  @Post(':id/return')
  async returnOrder(
    @Param('id') id: string,
    @Body() body: ReturnOrderDto,
    @Query() query: OrderQueryDto,
  ): Promise<Order> {
    const customerId = body.customerId ?? query.customerId
    return this.orderService.returnOrder(id, customerId, body.reason)
  }
}
